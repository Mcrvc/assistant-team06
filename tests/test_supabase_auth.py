import time
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from fastapi.testclient import TestClient

from assistant.api import create_app
from assistant.auth import SupabaseBearerAuth
from assistant.db import AppEnvConfig
from assistant.interview_store import SQLAlchemyInterviewRepository
from assistant.interviews import InterviewError, InterviewService

ISSUER = "https://unit-test.supabase.co/auth/v1"
USER = str(uuid4())


@pytest.fixture(params=["RS256", "ES256"])
def signer(request):
    alg = request.param
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048) if alg == "RS256" else ec.generate_private_key(ec.SECP256R1())
    serializer = jwt.algorithms.RSAAlgorithm if alg == "RS256" else jwt.algorithms.ECAlgorithm
    jwk = serializer.to_jwk(private.public_key(), as_dict=True)
    jwk.update(kid="test-key", alg=alg)
    class Keys:
        def get_signing_key_from_jwt(self, token):
            if jwt.get_unverified_header(token).get("kid") != "test-key":
                raise jwt.PyJWKClientError("unknown key")
            return jwt.PyJWK.from_dict(jwk)
    verifier = SupabaseBearerAuth(ISSUER, jwks_client=Keys())
    def sign(**changes):
        now = int(time.time())
        claims = {"sub": USER, "iss": ISSUER, "aud": "authenticated", "role": "authenticated",
                  "iat": now, "exp": now + 300, **changes}
        return jwt.encode(claims, private, algorithm=alg, headers={"kid": "test-key"})
    return verifier, sign


def test_valid_signature_and_claims_yield_verified_subject(signer):
    verifier, sign = signer
    assert verifier.authenticate("Bearer " + sign()) == USER


@pytest.mark.parametrize("claims", [
    {"exp": 1}, {"iss": "https://wrong.supabase.co/auth/v1"}, {"aud": "other-app"},
    {"role": "service_role"}, {"sub": "not-a-user-id"}, {"iat": 9999999999}, {"exp": None},
])
def test_invalid_claims_are_rejected_without_exposing_token(signer, claims):
    verifier, sign = signer
    token = sign(**claims)
    with pytest.raises(InterviewError) as exc:
        verifier.authenticate("Bearer " + token)
    assert exc.value.status == 401 and token not in exc.value.message


def test_unsigned_shared_secret_and_wrong_signatures_are_rejected(signer):
    verifier, sign = signer
    for token in [jwt.encode({"sub": USER}, "", algorithm="none"),
                  jwt.encode({"sub": USER}, "unit-test-secret" * 3, algorithm="HS256"),
                  sign()[:-12] + "notthesignature"]:
        with pytest.raises(InterviewError) as exc:
            verifier.authenticate("Bearer " + token)
        assert exc.value.status == 401


def test_missing_token_and_unknown_kid(signer):
    verifier, sign = signer
    for header in ["", "Basic abc", "Bearer", "Bearer " + "x" * 16001]:
        with pytest.raises(InterviewError) as exc:
            verifier.authenticate(header)
        assert exc.value.status == 401
    import base64
    import json
    parts = sign().split(".")
    header = jwt.get_unverified_header(".".join(parts))
    header["kid"] = "unknown-key"
    parts[0] = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
    with pytest.raises(InterviewError) as exc:
        verifier.authenticate("Bearer " + ".".join(parts))
    assert exc.value.status == 401


def test_jwks_outage_is_retryable_503(signer):
    verifier, sign = signer
    class OfflineKeys:
        def get_signing_key_from_jwt(self, token):
            raise jwt.PyJWKClientConnectionError("private connection details")
    verifier.jwks_client = OfflineKeys()
    with pytest.raises(InterviewError) as exc:
        verifier.authenticate("Bearer " + sign())
    assert exc.value.status == 503 and "private" not in exc.value.message


def test_http_auth_and_owner_isolation_with_signed_tokens(tmp_path, signer):
    verifier, sign = signer
    repository = SQLAlchemyInterviewRepository.local(tmp_path / "auth.sqlite")
    app = create_app(service=InterviewService(repository), demo_enabled=False, token_auth=verifier)
    try:
        with TestClient(app) as client:
            assert client.post("/api/interviews", json={"job_profile": {"title": "Intern"}}).status_code == 401
            client.headers["Authorization"] = "Bearer " + sign()
            response = client.post("/api/interviews", json={"job_profile": {"title": "Intern"}})
            assert response.status_code == 201
            path = f'/api/interviews/{response.json()["id"]}'
            client.headers["Authorization"] = "Bearer " + sign(sub=str(uuid4()))
            assert client.get(path).status_code == 404
            client.headers["Authorization"] = "Bearer " + sign(exp=1)
            assert client.get(path).status_code == 401
    finally:
        repository.close()


def test_config_cannot_mix_projects_or_use_non_https_issuer():
    config = AppEnvConfig("https://one.supabase.co", "", "", "https://two.supabase.co/auth/v1/.well-known/jwks.json")
    with pytest.raises(ValueError):
        SupabaseBearerAuth.from_config(config)
    with pytest.raises(ValueError):
        SupabaseBearerAuth("http://untrusted.example/auth/v1")
