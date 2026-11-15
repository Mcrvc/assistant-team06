"""CV PDF text extraction and Job Profile parsing (URL fetch + HTML/text cleanup)."""
from __future__ import annotations

import io
import ipaddress
import re
import socket
from urllib.parse import urlsplit

from assistant.ai import AiError, _readable_text, fetch_page
from assistant.interview_schemas import JobProfile
from assistant.interviews import InterviewError

MAX_PDF_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_CV_CHARS = 20_000
MAX_JOB_CHARS = 12_000
JOB_FETCH_TIMEOUT_S = 8.0

_HTML_TAG_RE = re.compile(
    r"<(?:!doctype|html|head|body|div|p|br|span|ul|ol|li|h[1-6]|section|article|table|tr|td|th|script|style|a)\b[^>]*>",
    re.IGNORECASE,
)
_URL_LINE_RE = re.compile(r"^https?://\S+$", re.IGNORECASE)
_BLOCKED_HOST_SUFFIXES = (".localhost", ".local", ".internal", ".localdomain")


def _normalize_whitespace(text: str) -> str:
    text = text.replace("\x00", "")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def extract_pdf_text(
    data: bytes,
    *,
    max_bytes: int = MAX_PDF_BYTES,
    max_chars: int = MAX_CV_CHARS,
) -> tuple[str, bool]:
    """Extract readable text from an uploaded PDF file.

    Returns ``(text, truncated)`` or raises ``InterviewError(400, ...)``.
    """
    if not data:
        raise InterviewError(400, "empty_pdf", "Uploaded PDF file is empty. Please upload a valid PDF or paste your CV text.")
    if len(data) > max_bytes:
        raise InterviewError(400, "pdf_too_large", "PDF file exceeds the 5 MB limit. Please upload a smaller file or paste your CV text.")
    if not data.lstrip().startswith(b"%PDF-"):
        raise InterviewError(400, "invalid_pdf", "Invalid PDF file. Please upload a valid .pdf file or paste your CV text.")

    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - dependency misconfiguration
        raise InterviewError(503, "pdf_parser_unavailable", "PDF parser is not installed on the server.") from exc

    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            try:
                if not reader.decrypt(""):
                    raise ValueError("Encrypted PDF")
            except Exception as exc:
                raise InterviewError(
                    400,
                    "pdf_unreadable",
                    "This PDF is password-protected. Please unlock it or paste your CV text instead.",
                ) from exc
        pages = [page.extract_text() or "" for page in reader.pages]
    except InterviewError:
        raise
    except Exception as exc:
        raise InterviewError(
            400,
            "pdf_unreadable",
            "Could not read this PDF file. Please check the file or paste your CV text instead.",
        ) from exc

    text = _normalize_whitespace("\n\n".join(pages))
    if not text:
        raise InterviewError(
            400,
            "pdf_no_text",
            "No selectable text found in this PDF (it may be a scanned image). Please paste your CV text instead.",
        )
    truncated = len(text) > max_chars
    return text[:max_chars], truncated


def _is_public_ip(ip_str: str) -> bool:
    ip = ipaddress.ip_address(ip_str)
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def validate_public_url(url: str) -> str:
    """Ensure ``url`` is an external http(s) URL and not an internal/private target."""
    candidate = url.strip()
    parts = urlsplit(candidate)
    if parts.scheme.lower() not in ("http", "https") or not parts.hostname:
        raise InterviewError(
            400,
            "invalid_job_url",
            "Invalid job URL. Please use an http(s) link or paste the job description manually.",
        )
    if parts.username or parts.password:
        raise InterviewError(
            400,
            "invalid_job_url",
            "Job URLs with embedded credentials are not allowed. Please paste the job description manually.",
        )

    host = parts.hostname.lower().rstrip(".")
    if host == "localhost" or any(host.endswith(suffix) for suffix in _BLOCKED_HOST_SUFFIXES):
        raise InterviewError(
            400,
            "invalid_job_url",
            "Internal or local URLs are not allowed. Please paste the job description manually.",
        )

    try:
        ipaddress.ip_address(host)
    except ValueError:
        port = parts.port or (443 if parts.scheme.lower() == "https" else 80)
        try:
            infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise InterviewError(
                400,
                "job_profile_unreadable",
                "Could not reach that job link. Please copy and paste the job description manually.",
            ) from exc
        resolved_ips = {info[4][0].split("%", 1)[0] for info in infos if info[4]}
        if not resolved_ips or any(not _is_public_ip(ip) for ip in resolved_ips):
            raise InterviewError(
                400,
                "invalid_job_url",
                "Internal or private URLs are not allowed. Please paste the job description manually.",
            )
    else:
        if not _is_public_ip(host):
            raise InterviewError(
                400,
                "invalid_job_url",
                "Internal or private URLs are not allowed. Please paste the job description manually.",
            )

    return candidate


def clean_job_text(raw: str, *, max_chars: int = MAX_JOB_CHARS) -> str:
    """Strip HTML tags/scripts when present, normalize whitespace, and truncate."""
    text = raw.strip()
    if not text:
        return ""
    if _HTML_TAG_RE.search(text):
        text = _readable_text(text, max_chars)
    text = _normalize_whitespace(text)
    return text[:max_chars]


def parse_job_profile(job_profile: JobProfile, *, timeout_s: float = JOB_FETCH_TIMEOUT_S) -> JobProfile:
    """Resolve a JobProfile's ``description`` (URL, HTML, or plain text) into clean text."""
    raw_desc = (job_profile.description or "").strip()
    if not raw_desc:
        return job_profile

    if _URL_LINE_RE.match(raw_desc):
        safe_url = validate_public_url(raw_desc)
        try:
            chunk = fetch_page(safe_url, timeout_s=timeout_s)
        except AiError as exc:
            raise InterviewError(
                400,
                "job_profile_unreadable",
                "Could not read content from that job link. Please copy and paste the job description manually.",
            ) from exc
        cleaned = _normalize_whitespace(chunk.text)[:MAX_JOB_CHARS]
    else:
        cleaned = clean_job_text(raw_desc, max_chars=MAX_JOB_CHARS)

    if not cleaned and not job_profile.title.strip():
        raise InterviewError(
            400,
            "job_profile_unreadable",
            "Could not extract readable job description text. Please paste the job description manually.",
        )

    return job_profile.model_copy(update={"description": cleaned})
