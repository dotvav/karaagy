"""OpenAI-compatible Assistants / Threads API request and response schemas."""

import time
from typing import Any, Literal

from pydantic import BaseModel, Field

from karaagy.models.openai import UsageInfo


class ThreadObject(BaseModel):
    """OpenAI Thread object schema."""

    id: str
    object: Literal["thread"] = "thread"
    created_at: int = Field(default_factory=lambda: int(time.time()))
    metadata: dict[str, Any] = Field(default_factory=dict)
    conversation_id: str | None = None  # Underlying AGY conversation ID


class ThreadDeletedResponse(BaseModel):
    """OpenAI Thread deletion confirmation schema."""

    id: str
    object: Literal["thread.deleted"] = "thread.deleted"
    deleted: bool = True


class ThreadMessageContentText(BaseModel):
    """Text content block for a thread message."""

    type: Literal["text"] = "text"
    text: dict[str, Any]  # e.g. {"value": "...", "annotations": []}


class ThreadMessageContentImage(BaseModel):
    """Image content block for a thread message."""

    type: Literal["image_url", "image_file"] = "image_url"
    image_url: dict[str, Any] | None = None
    image_file: dict[str, Any] | None = None


class ThreadMessage(BaseModel):
    """OpenAI Thread Message schema."""

    id: str
    object: Literal["thread.message"] = "thread.message"
    created_at: int = Field(default_factory=lambda: int(time.time()))
    thread_id: str
    role: Literal["user", "assistant"]
    content: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ThreadMessageList(BaseModel):
    """OpenAI Thread Message list container."""

    object: Literal["list"] = "list"
    data: list[ThreadMessage]
    first_id: str | None = None
    last_id: str | None = None
    has_more: bool = False


class CreateThreadMessageRequest(BaseModel):
    """Request schema for posting a new message to a thread."""

    model_config = {"extra": "allow"}

    role: Literal["user", "assistant"] = "user"
    content: str | list[dict[str, Any]]
    metadata: dict[str, Any] | None = None


class CreateThreadRequest(BaseModel):
    """Request schema for creating a new thread."""

    model_config = {"extra": "allow"}

    messages: list[CreateThreadMessageRequest] | None = None
    metadata: dict[str, Any] | None = None


class CreateRunRequest(BaseModel):
    """Request schema for running a thread."""

    model_config = {"extra": "allow"}

    assistant_id: str | None = None
    model: str | None = None
    instructions: str | None = None
    additional_instructions: str | None = None
    additional_messages: list[CreateThreadMessageRequest] | None = None
    stream: bool = False
    effort: Literal["low", "medium", "high"] | None = None


class CreateThreadAndRunRequest(BaseModel):
    """Request schema for creating a thread and executing a run in a single request."""

    model_config = {"extra": "allow"}

    assistant_id: str | None = None
    thread: CreateThreadRequest | None = None
    model: str | None = None
    instructions: str | None = None
    additional_instructions: str | None = None
    additional_messages: list[CreateThreadMessageRequest] | None = None
    stream: bool = False
    effort: Literal["low", "medium", "high"] | None = None


class RunObject(BaseModel):
    """OpenAI Thread Run object schema."""

    id: str
    object: Literal["thread.run"] = "thread.run"
    created_at: int = Field(default_factory=lambda: int(time.time()))
    thread_id: str
    assistant_id: str | None = None
    status: Literal["queued", "in_progress", "completed", "failed", "cancelled"] = "completed"
    model: str
    instructions: str | None = None
    usage: UsageInfo | None = None
    last_error: str | None = None
