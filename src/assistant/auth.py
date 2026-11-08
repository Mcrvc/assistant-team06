"""Supabase access-token verification for the team's existing browser Auth flow."""
from __future__ import annotations

from urllib.parse import urlsplit
from uuid import UUID

import jwt
from jwt import PyJWKClient

from assistant.db import AppEnvConfig, _is_real_value
from assistant.interviews import InterviewError


class SupabaseBearerAuth:
    def __init__(self, issuer: str, *, jwks_client=None) -> None:
        url = urlsplit(issuer)
        if url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ValueError("Supabase issuer must be a trusted HTTPS URL")
        self.issuer = issuer.rstrip("/")
        self.jwks_client = jwks_client or PyJWKClient(
            self.issuer + "/.well-known/jwks.json", timeout=5, lifespan=300,
        )

    @classmethod
    def from_config(cls, config: AppEnvConfig) -> SupabaseBearerAuth | None:
        if not _is_real_value(config.supabase_url):
            return None
        issuer = config.supabase_url.rstrip("/") + "/auth/v1"
        expected = issuer + "/.well-known/jwks.json"
        if _is_real_value(config.supabase_jwks_url) and config.supabase_jwks_url != expected:
            raise ValueError("SUPABASE_JWKS_URL must match the configured Supabase project")
        return cls(issuer)

    def authenticate(self, authorization: str) -> str:
        parts = authorization.split()
        if len(parts) != 2 or parts[0].lower() != "bearer" or len(parts[1]) > 16000:
            raise InterviewError(401, "authentication_required", "A valid Supabase access token is required")
        token = parts[1]
        try:
            header = jwt.get_unverified_header(token)
            if (header.get("alg") not in ("RS256", "ES256")
                    or not isinstance(header.get("kid"), str) or not 0 < len(header["kid"]) <= 200):
                raise jwt.InvalidTokenError("Unsupported signing algorithm or key")
            signing_key = self.jwks_client.get_signing_key_from_jwt(token)
            if signing_key.algorithm_name != header["alg"]:
                raise jwt.InvalidTokenError("Key algorithm mismatch")
            claims = jwt.decode(
                token, signing_key.key, algorithms=["RS256", "ES256"],
                audience="authenticated", issuer=self.issuer, leeway=10,
                options={"require": ["exp", "iat", "iss", "aud", "sub"]},
            )
            if (claims.get("role") != "authenticated" or type(claims["exp"]) is not int
                    or type(claims["iat"]) is not int or not isinstance(claims["sub"], str)):
                raise jwt.InvalidTokenError("Invalid user claims")
            return str(UUID(claims["sub"]))
        except jwt.PyJWKClientConnectionError:
            raise InterviewError(503, "authentication_unavailable", "Cannot verify sign-in right now; retry later") from None
        except (jwt.PyJWTError, ValueError, TypeError, KeyError):
            raise InterviewError(401, "invalid_access_token", "Access token is invalid or expired") from None
