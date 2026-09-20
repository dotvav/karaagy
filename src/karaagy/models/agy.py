"""Pydantic schemas for Antigravity CLI json and stream-json event outputs."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class AGYUsage(BaseModel):
    """Antigravity token usage structure."""

    input_tokens: int = 0
    output_tokens: int = 0
    thinking_tokens: int = 0
    cache_read_tokens: int = 0
    total_tokens: int = 0


class AGYJsonResponse(BaseModel):
    """Payload returned by `agy --output-format json`."""

    conversation_id: str | None = None
    status: str = "SUCCESS"
    response: str = ""
    error: str | None = None
    duration_seconds: float = 0.0
    num_turns: int = 1
    usage: AGYUsage | None = None


class AGYStepUpdate(BaseModel):
    """Payload for `step_update` events in stream-json."""

    conversation_id: str | None = None
    step_index: int = 0
    state: str = "ACTIVE"
    step_type: str = "agent_response"
    text_delta: str | None = None
    duration_seconds: float | None = None
    usage: AGYUsage | None = None


class AGYResultEvent(BaseModel):
    """Payload for `result` event in stream-json."""

    conversation_id: str | None = None
    status: str = "SUCCESS"
    response: str = ""
    error: str | None = None
    duration_seconds: float = 0.0
    num_turns: int = 1
    usage: AGYUsage | None = None


class AGYStreamEvent(BaseModel):
    """Envelope for NDJSON lines from `agy --output-format stream-json`."""

    event: Literal["init", "step_update", "result", "error", "unknown"] = "unknown"
    conversation_id: str | None = None
    step_update: AGYStepUpdate | None = None
    result: AGYResultEvent | None = None
    init: dict[str, Any] | None = None
    extra: dict[str, Any] = Field(default_factory=dict)
