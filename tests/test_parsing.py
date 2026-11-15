"""Tests for CV PDF parsing and Job Profile parsing (URL/HTML/text + SSRF)."""
from __future__ import annotations

import socket
from fastapi.testclient import TestClient
import pytest

from assistant.ai import AiResponseError, AiTimeoutError, ContextChunk
from assistant.interview_ai import MockInterviewAI
from assistant.interview_schemas import JobProfile
from assistant.interview_store import SQLAlchemyInterviewRepository
from assistant.interviews import InterviewError, InterviewService
from assistant.parsing import clean_job_text, extract_pdf_text, parse_job_profile, validate_public_url
from assistant.user_api import InMemoryProfileStore
from assistant.web import create_app


def _make_pdf_bytes(text: str = "") -> bytes:
    """Build a minimal valid single-page PDF containing ``text``."""
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET\n" if text else ""
    stream_bytes = stream.encode("latin-1")
    objects = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        (
            b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
        ),
        b"4 0 obj\n<< /Length " + str(len(stream_bytes)).encode() + b" >>\nstream\n" + stream_bytes + b"endstream\nendobj\n",
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(out))
        out.extend(obj)
    xref_pos = len(out)
    out.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode())
    out.extend(
        f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode()
    )
    return bytes(out)


def _client(tmp_path) -> TestClient:
    service = InterviewService(SQLAlchemyInterviewRepository.local(tmp_path / "parsing.sqlite"), MockInterviewAI())
    app = create_app(
        service=service,
        auth_resolver=lambda _req: "00000000-0000-0000-0000-000000000001",
        profile_store=InMemoryProfileStore(),
    )
    return TestClient(app)


def test_extract_pdf_text_reads_valid_pdf():
    pdf = _make_pdf_bytes("Nguyen Van A - Backend Engineer")
    text, truncated = extract_pdf_text(pdf)
    assert "Nguyen Van A - Backend Engineer" in text
    assert truncated is False


def test_extract_pdf_text_truncates_and_rejects_bad_inputs():
    long_pdf = _make_pdf_bytes("A" * 100)
    text, truncated = extract_pdf_text(long_pdf, max_chars=20)
    assert len(text) == 20
    assert truncated is True

    with pytest.raises(InterviewError) as exc_empty:
        extract_pdf_text(b"")
    assert exc_empty.value.status == 400

    with pytest.raises(InterviewError) as exc_invalid:
        extract_pdf_text(b"not a pdf")
    assert exc_invalid.value.status == 400

    with pytest.raises(InterviewError) as exc_big:
        extract_pdf_text(b"%PDF-1.4\n" + b"0" * 50, max_bytes=20)
    assert exc_big.value.status == 400

    with pytest.raises(InterviewError) as exc_blank:
        extract_pdf_text(_make_pdf_bytes(""))
    assert exc_blank.value.status == 400
    assert exc_blank.value.code == "pdf_no_text"


@pytest.mark.parametrize(
    "bad_url",
    [
        "file:///etc/passwd",
        "ftp://example.com/job",
        "http://localhost:8000/secret",
        "http://127.0.0.1/admin",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.1/internal",
        "http://192.168.1.10/job",
        "http://[::1]/admin",
        "https://user:pass@example.com/job",
    ],
)
def test_validate_public_url_blocks_internal_and_invalid_urls(bad_url: str):
    with pytest.raises(InterviewError) as exc:
        validate_public_url(bad_url)
    assert exc.value.status == 400


def test_validate_public_url_blocks_dns_resolving_to_private_ip(monkeypatch):
    def fake_getaddrinfo(host, port, type=0):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", port))]

    monkeypatch.setattr("assistant.parsing.socket.getaddrinfo", fake_getaddrinfo)
    with pytest.raises(InterviewError) as exc:
        validate_public_url("https://internal.example.com/job")
    assert exc.value.status == 400


def test_validate_public_url_allows_public_ip(monkeypatch):
    def fake_getaddrinfo(host, port, type=0):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))]

    monkeypatch.setattr("assistant.parsing.socket.getaddrinfo", fake_getaddrinfo)
    assert validate_public_url("https://example.com/jobs/123") == "https://example.com/jobs/123"


def test_clean_job_text_strips_html_and_preserves_plain_comparisons():
    html_job = "<div><h1>Backend Engineer</h1><script>alert(1)</script><p>Python &amp; SQL</p></div>"
    cleaned = clean_job_text(html_job)
    assert "Backend Engineer" in cleaned
    assert "Python & SQL" in cleaned
    assert "alert" not in cleaned
    assert "<div>" not in cleaned

    plain = "Need < 2 years of Python experience"
    assert clean_job_text(plain) == plain
    assert len(clean_job_text("X" * 50, max_chars=15)) == 15


def test_parse_job_profile_fetches_url_and_returns_400_on_failure(monkeypatch):
    monkeypatch.setattr(
        "assistant.parsing.socket.getaddrinfo",
        lambda host, port, type=0: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))],
    )
    monkeypatch.setattr(
        "assistant.parsing.fetch_page",
        lambda url, timeout_s=None: ContextChunk(text="Senior Python Engineer at Acme", source=url, score=1.0),
    )
    parsed = parse_job_profile(JobProfile(description="https://example.com/jobs/1"))
    assert parsed.description == "Senior Python Engineer at Acme"

    def fail_fetch(url, timeout_s=None):
        raise AiTimeoutError("timed out")

    monkeypatch.setattr("assistant.parsing.fetch_page", fail_fetch)
    with pytest.raises(InterviewError) as exc:
        parse_job_profile(JobProfile(description="https://example.com/jobs/1"))
    assert exc.value.status == 400
    assert exc.value.code == "job_profile_unreadable"


def test_parse_cv_pdf_endpoint_and_create_interview_parsing(monkeypatch, tmp_path):
    client = _client(tmp_path)
    pdf = _make_pdf_bytes("Tran Bao Anh Python FastAPI")
    resp = client.post("/api/cv/parse-pdf", files={"file": ("cv.pdf", pdf, "application/pdf")})
    assert resp.status_code == 200
    body = resp.json()
    assert "Tran Bao Anh Python FastAPI" in body["text"]
    assert body["truncated"] is False

    bad_resp = client.post("/api/cv/parse-pdf", files={"file": ("cv.pdf", b"not-a-pdf", "application/pdf")})
    assert bad_resp.status_code == 400
    assert bad_resp.json()["error"]["code"] == "invalid_pdf"

    # Internal URL returns 400 with clear message
    bad_job = client.post(
        "/api/interviews",
        json={"job_profile": {"description": "http://127.0.0.1:8000/secret"}, "cv": body["text"]},
    )
    assert bad_job.status_code == 400
    assert bad_job.json()["error"]["code"] == "invalid_job_url"

    # Unreachable external URL returns 400
    monkeypatch.setattr(
        "assistant.parsing.socket.getaddrinfo",
        lambda host, port, type=0: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))],
    )
    monkeypatch.setattr(
        "assistant.parsing.fetch_page",
        lambda url, timeout_s=None: (_ for _ in ()).throw(AiResponseError("empty")),
    )
    fail_job = client.post(
        "/api/interviews",
        json={"job_profile": {"description": "https://example.com/bad-job"}, "cv": body["text"]},
    )
    assert fail_job.status_code == 400
    assert fail_job.json()["error"]["code"] == "job_profile_unreadable"

    # HTML job description is cleaned before saving
    ok_job = client.post(
        "/api/interviews",
        json={"job_profile": {"description": "<p>Data Engineer</p><script>x()</script>"}, "cv": body["text"]},
    )
    assert ok_job.status_code == 201
    interview_id = ok_job.json()["id"]
    view = client.get(f"/api/interviews/{interview_id}").json()
    assert view["job_profile"]["description"] == "Data Engineer"
    assert view["cv"] == body["text"]
