"""Response sanitization and retry error detection."""

import json
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


def strip_json_fences(text: str) -> str:
    """Extract raw JSON content by stripping markdown code fences and surrounding prose."""
    if not text:
        return ""

    cleaned = text.strip()

    # 1. Fast-path: already valid JSON
    try:
        json.loads(cleaned)
        return cleaned
    except (json.JSONDecodeError, TypeError):
        pass

    # 2. Outer markdown code fence stripping (greedy to preserve inner backticks)
    outer_fence_pattern = re.compile(
        r"^```(?:json|JSON)?\s*\n?([\s\S]*)\n?\s*```$",
        re.DOTALL,
    )
    outer_match = outer_fence_pattern.match(cleaned)
    if outer_match:
        inner = outer_match.group(1).strip()
        try:
            json.loads(inner)
            return inner
        except (json.JSONDecodeError, TypeError):
            pass

    # 3. Search for embedded code fences containing valid JSON
    embedded_fence_pattern = re.compile(
        r"```(?:json|JSON)?\s*\n?([\s\S]*?)\n?\s*```",
        re.DOTALL,
    )
    for fence_match in embedded_fence_pattern.finditer(cleaned):
        candidate = fence_match.group(1).strip()
        try:
            json.loads(candidate)
            return candidate
        except (json.JSONDecodeError, TypeError):
            continue

    # 4. Outermost {...} or [...] structural extraction:
    # check both object ({ to }) and array ([ to ]) boundaries
    # (taking whichever valid JSON span starts earlier or encompasses the payload) and validate with json.loads.
    structural_candidates: list[str] = []
    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")
    has_brace = first_brace != -1 and last_brace > first_brace

    first_bracket = cleaned.find("[")
    last_bracket = cleaned.rfind("]")
    has_bracket = first_bracket != -1 and last_bracket > first_bracket

    if has_brace and has_bracket:
        if first_brace <= first_bracket:
            structural_candidates = [
                cleaned[first_brace : last_brace + 1].strip(),
                cleaned[first_bracket : last_bracket + 1].strip(),
            ]
        else:
            structural_candidates = [
                cleaned[first_bracket : last_bracket + 1].strip(),
                cleaned[first_brace : last_brace + 1].strip(),
            ]
    elif has_brace:
        structural_candidates = [cleaned[first_brace : last_brace + 1].strip()]
    elif has_bracket:
        structural_candidates = [cleaned[first_bracket : last_bracket + 1].strip()]

    for candidate in structural_candidates:
        try:
            json.loads(candidate)
            return candidate
        except (json.JSONDecodeError, TypeError):
            pass

    # 5. Fallback if outer fence matched even when json.loads failed
    if outer_match:
        return outer_match.group(1).strip()

    # Fallback: strip unclosed leading/trailing fences
    unclosed_fence = re.sub(r"^```(?:json|JSON)?\s*\n?", "", cleaned)
    unclosed_fence = re.sub(r"\n?\s*```\s*$", "", unclosed_fence)
    return unclosed_fence.strip()


def sanitize_agy_response(text: str, expect_json: bool = False) -> str:
    """Strip internal AGY background task notifications, execution headers, and optionally markdown code fences."""
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
    cleaned = cleaned.strip()

    if expect_json:
        cleaned = strip_json_fences(cleaned)

    return cleaned
