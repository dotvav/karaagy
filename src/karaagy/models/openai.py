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


class ResponseFormatJsonSchema(BaseModel):
    """OpenAI JSON Schema specification."""

    model_config = {"extra": "allow", "populate_by_name": True}

    name: str = "response_schema"
    description: str | None = None
    schema_: dict[str, Any] | None = Field(default=None, alias="schema")
    strict: bool | None = None


class ResponseFormat(BaseModel):
    """OpenAI response_format payload."""

    model_config = {"extra": "allow"}

    type: Literal["text", "json_object", "json_schema"] = "text"
    json_schema: ResponseFormatJsonSchema | dict[str, Any] | None = None


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
    response_format: ResponseFormat | dict[str, Any] | None = None

    # Antigravity extensions
    effort: Literal["low", "medium", "high"] | None = None
    conversation_id: str | None = None


def is_json_response_format(response_format: ResponseFormat | dict[str, Any] | None) -> bool:
    """Return True if response_format requires JSON output (json_object or json_schema)."""
    if not response_format:
        return False
    if isinstance(response_format, ResponseFormat):
        return response_format.type in ("json_object", "json_schema")
    if isinstance(response_format, dict):
        return response_format.get("type") in ("json_object", "json_schema")
    return False


def extract_json_schema(
    response_format: ResponseFormat | dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Extract the raw JSON Schema dict from response_format."""
    if not response_format:
        return None

    if isinstance(response_format, ResponseFormat):
        if response_format.type != "json_schema" or response_format.json_schema is None:
            return None
        if isinstance(response_format.json_schema, ResponseFormatJsonSchema):
            if response_format.json_schema.schema_ is not None:
                return response_format.json_schema.schema_
            if response_format.json_schema.model_extra:
                return response_format.json_schema.model_extra
            return None
        if isinstance(response_format.json_schema, dict):
            return response_format.json_schema.get("schema") or response_format.json_schema

    if isinstance(response_format, dict):
        if response_format.get("type") != "json_schema":
            return None
        if "json_schema" in response_format and isinstance(response_format["json_schema"], dict):
            js = response_format["json_schema"]
            return js.get("schema") or js
        if "schema" in response_format and isinstance(response_format["schema"], dict):
            return response_format["schema"]

    return None


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
    conversation_id: str | None = None


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


class ImageGenerationRequest(BaseModel):
    """OpenAI standard image generation request schema."""

    model_config = {"extra": "allow"}

    prompt: str
    model: str | None = None
    n: int | None = 1
    quality: str | None = "standard"
    response_format: Literal["url", "b64_json"] | str | None = "url"
    size: str | None = "1024x1024"
    style: str | None = None
    user: str | None = None


class ImageObject(BaseModel):
    """Single generated image data representation."""

    b64_json: str | None = None
    url: str | None = None
    revised_prompt: str | None = None


class ImagesResponse(BaseModel):
    """OpenAI standard images response envelope."""

    created: int = Field(default_factory=lambda: int(time.time()))
    data: list[ImageObject]
