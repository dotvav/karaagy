"""Response sanitization and retry error detection."""

import re

RETRYABLE_AGY_ERROR_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"Eligibility check failed", re.IGNORECASE),
    re.compile(r"failed to get profile picture", re.IGNORECASE),
    re.compile(r"unexpected EOF", re.IGNORECASE),
    re.compile(r"connection reset", re.IGNORECASE),
    re.compile(r"broken pipe", re.IGNORECASE),
    re.compile(r"timeout", re.IGNORECASE),
    re.compile(r"timed out", re.IGNORECASE),
    re.compile(r"deadline exceeded", re.IGNORECASE),
    re.compile(r"temporary failure in name resolution", re.IGNORECASE),
    re.compile(r"rate limit", re.IGNORECASE),
    re.compile(r"resource exhausted", re.IGNORECASE),
    re.compile(r"quota", re.IGNORECASE),
    re.compile(r"429", re.IGNORECASE),
    re.compile(r"500", re.IGNORECASE),
    re.compile(r"502", re.IGNORECASE),
    re.compile(r"503", re.IGNORECASE),
    re.compile(r"504", re.IGNORECASE),
    re.compile(r"overloaded", re.IGNORECASE),
    re.compile(r"TLS handshake", re.IGNORECASE),
    re.compile(r"oauth", re.IGNORECASE),
    re.compile(r"token expired", re.IGNORECASE),
    re.compile(r"subscriber fell behind", re.IGNORECASE),
    re.compile(r"stalled for", re.IGNORECASE),
    re.compile(r"interrupted", re.IGNORECASE),
    re.compile(r"channel closed", re.IGNORECASE),
    re.compile(r"stream closed", re.IGNORECASE),
    re.compile(r"transport is closing", re.IGNORECASE),
    re.compile(r"empty response", re.IGNORECASE),
]


def is_retryable_agy_error(text: str) -> bool:
    """Check if an error output from AGY CLI corresponds to a transient network or OAuth glitch."""
    if not text:
        return False
    return any(pattern.search(text) for pattern in RETRYABLE_AGY_ERROR_PATTERNS)


def sanitize_agy_response(text: str) -> str:
    """Strip internal AGY background task notifications and raw tool dump markers from output."""
    if not text:
        return ""
    # Strip **Notification received:** ... ```...``` (with optional trailing ```)
    cleaned = re.sub(
        r"\*\*Notification received:\*\*\s*task\s+[`\w\-/]+\s+completed\.[\s\S]*?Task Output:\s*```(?:[^\n]*\n)?[\s\S]*?```(?:\s*```)?",
        "",
        text,
        flags=re.IGNORECASE,
    )
    # Strip any standalone Created At / Completed At CLI task headers if echoed
    cleaned = re.sub(
        r"Created At:\s*[\d\-:TZ]+\s*Completed At:\s*[\d\-:TZ]+[\s\S]*?Output:\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    return cleaned.strip()
