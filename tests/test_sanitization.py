"""Tests for response sanitization and retry error detection."""

from karaagy.core.sanitization import is_retryable_agy_error, sanitize_agy_response


def test_is_retryable_agy_error() -> None:
    """Test classification of transient / retryable AGY CLI errors."""
    assert is_retryable_agy_error("Eligibility check failed: unexpected EOF") is True
    assert is_retryable_agy_error("failed to get profile picture") is True
    assert is_retryable_agy_error("HTTP 429 Too Many Requests") is True
    assert is_retryable_agy_error("503 Service Unavailable") is True
    assert is_retryable_agy_error("Model is overloaded, please retry later") is True
    assert is_retryable_agy_error("TLS handshake error") is True
    assert is_retryable_agy_error("broken pipe") is True
    assert (
        is_retryable_agy_error(
            "the connection to the agent was interrupted before the response finished: subscriber fell behind updates, stalled for 5s"
        )
        is True
    )
    assert is_retryable_agy_error("channel closed") is True
    assert is_retryable_agy_error("invalid argument: unrecognized flag") is False
    assert is_retryable_agy_error("") is False


def test_sanitize_agy_response_notifications() -> None:
    """Test stripping internal AGY notification blocks."""
    raw = (
        "**Notification received:** task `task-12` completed.\n"
        "Task Output: ```some raw dump```\n\n"
        "Here is the actual answer."
    )
    cleaned = sanitize_agy_response(raw)
    assert "Notification received" not in cleaned
    assert "Here is the actual answer." in cleaned


def test_sanitize_agy_response_headers() -> None:
    """Test stripping CLI execution headers."""
    raw = "Created At: 2026-09-20T12:00:00Z Completed At: 2026-09-20T12:00:02Z Output: Paris is the capital of France."
    cleaned = sanitize_agy_response(raw)
    assert "Created At" not in cleaned
    assert "Paris is the capital of France." in cleaned
