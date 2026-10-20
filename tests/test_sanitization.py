"""Tests for response sanitization and retry error detection."""

import json

from karaagy.core.sanitization import (
    is_retryable_agy_error,
    sanitize_agy_response,
    strip_json_fences,
)


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


def test_strip_json_fences_fenced() -> None:
    """Test stripping standard markdown code fences (json, JSON, or untagged)."""
    assert strip_json_fences('```json\n{"a": 1}\n```') == '{"a": 1}'
    assert strip_json_fences('```JSON\n{"a": 1}\n```') == '{"a": 1}'
    assert strip_json_fences('```\n{"a": 1}\n```') == '{"a": 1}'


def test_strip_json_fences_raw_json() -> None:
    """Test raw JSON strings and JSON arrays without fences are preserved."""
    assert strip_json_fences('{"a": 1}') == '{"a": 1}'
    assert strip_json_fences('[{"a": 1}]') == '[{"a": 1}]'


def test_strip_json_fences_nested_code_blocks() -> None:
    """Test JSON containing nested markdown code fences inside string values."""
    payload = {"snippet": "```python\nprint(1)\n```"}
    serialized = json.dumps(payload)
    fenced = f"```json\n{serialized}\n```"

    result = strip_json_fences(fenced)
    assert result == serialized
    assert json.loads(result) == payload


def test_strip_json_fences_conversational_wrapping() -> None:
    """Test conversational preamble/postscript around fenced and unfenced JSON."""
    fenced_conversational = 'Here is the JSON:\n```json\n{"ok": true}\n```\nHope this helps!'
    assert strip_json_fences(fenced_conversational) == '{"ok": true}'

    unfenced_conversational = 'Sure! {"ok": true}'
    assert strip_json_fences(unfenced_conversational) == '{"ok": true}'

    unfenced_array = 'Here is the data: [{"id": 42}]'
    assert strip_json_fences(unfenced_array) == '[{"id": 42}]'

    # Nested backtick payload with conversational text
    payload = {"snippet": "```python\nprint(1)\n```"}
    serialized = json.dumps(payload)
    conversational_nested = f"Here is the result:\n```json\n{serialized}\n```\nHope this helps!"
    assert strip_json_fences(conversational_nested) == serialized
    assert json.loads(strip_json_fences(conversational_nested)) == payload


def test_strip_json_fences_fallbacks() -> None:
    """Test fallbacks for partial, truncated, or empty input."""
    assert strip_json_fences("") == ""
    assert strip_json_fences("   ") == ""
    # Unclosed leading fence with valid JSON inside
    assert strip_json_fences('```json\n{"a": 1}') == '{"a": 1}'
    # Outer fence with truncated / malformed JSON
    assert strip_json_fences('```json\n{"a": \n```') == '{"a":'
    # Unclosed leading fence with truncated / malformed JSON
    assert strip_json_fences('```json\n{"a": ') == '{"a":'


def test_sanitize_agy_response_expect_json() -> None:
    """Test sanitize_agy_response with expect_json=True strips notifications, headers, and code fences."""
    raw = (
        "**Notification received:** task `task-42` completed.\n"
        "Task Output: ```dump```\n\n"
        "```json\n"
        '{"ok": true}\n'
        "```"
    )
    cleaned = sanitize_agy_response(raw, expect_json=True)
    assert cleaned == '{"ok": true}'

    raw_header = (
        "Created At: 2026-09-20T12:00:00Z Completed At: 2026-09-20T12:00:02Z Output: "
        '```json\n{"status": "success"}\n```'
    )
    cleaned_header = sanitize_agy_response(raw_header, expect_json=True)
    assert cleaned_header == '{"status": "success"}'


def test_sanitize_agy_response_expect_json_false() -> None:
    """Test sanitize_agy_response with expect_json=False preserves code fences untouched."""
    fenced_json = '```json\n{"ok": true}\n```'
    assert sanitize_agy_response(fenced_json, expect_json=False) == fenced_json
    assert sanitize_agy_response(fenced_json) == fenced_json

    markdown_code = "Here is some code:\n```python\nprint(1)\n```"
    assert sanitize_agy_response(markdown_code, expect_json=False) == markdown_code
    assert sanitize_agy_response(markdown_code) == markdown_code
