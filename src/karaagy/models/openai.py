"""OpenAI-compatible request and response schemas."""

import time
from typing import Any, Literal

from pydantic import BaseModel, Field

RoleType = Literal["system", "user", "assistant", "developer", "tool", "function"]


class ChatCompletionMessage(BaseModel):
    """A single chat message in a completion conversation (supports text and multimodal parts)."""

    role: str
    content: str | list[dict[str, Any]] | None = ""
    name: str | None = None


class ChatCompletionRequest(BaseModel):
    """OpenAI chat completion request schema with Antigravity extensions."""

    model_config = {"extra": "allow"}

    model: str
    messages: list[ChatCompletionMessage]
    stream: bool = False
    temperature: float | None = None
    top_p: float | None = None
    n: int | None = 1
    max_tokens: int | None = None
    stop: list[str] | str | None = None
    presence_penalty: float | None = None
    frequency_penalty: float | None = None
    user: str | None = None
    response_format: dict[str, Any] | None = None

    # Antigravity extensions
    effort: Literal["low", "medium", "high"] | None = None
    conversation_id: str | None = None


class UsageInfo(BaseModel):
    """Token usage counters."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionChoice(BaseModel):
    """Single completion candidate."""

    index: int = 0
    message: ChatCompletionMessage
    finish_reason: str | None = "stop"


class ChatCompletionResponse(BaseModel):
    """OpenAI standard non-streaming chat completion response."""

    id: str
    object: Literal["chat.completion"] = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: list[ChatCompletionChoice]
    usage: UsageInfo | None = None


class ChatCompletionChunkDelta(BaseModel):
    """Streamed token delta chunk."""

    role: str | None = None
    content: str | None = None


class ChatCompletionChunkChoice(BaseModel):
    """Choice within a streaming chunk."""

    index: int = 0
    delta: ChatCompletionChunkDelta
    finish_reason: str | None = None


class ChatCompletionChunk(BaseModel):
    """OpenAI standard streaming SSE event chunk."""

    id: str
    object: Literal["chat.completion.chunk"] = "chat.completion.chunk"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: list[ChatCompletionChunkChoice]
    usage: UsageInfo | None = None


class ModelCard(BaseModel):
    """OpenAI model metadata."""

    id: str
    object: Literal["model"] = "model"
    created: int = 1700000000
    owned_by: str = "antigravity"


class ModelList(BaseModel):
    """OpenAI list of models."""

    object: Literal["list"] = "list"
    data: list[ModelCard]


class ErrorDetail(BaseModel):
    """OpenAI error structure."""

    message: str
    type: str = "invalid_request_error"
    param: str | None = None
    code: str | None = None


class ErrorResponse(BaseModel):
    """OpenAI error response envelope."""

    error: ErrorDetail
