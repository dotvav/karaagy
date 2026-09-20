"""OpenAI Chat Completions endpoint supporting sync and SSE streaming."""

import logging
from typing import Any

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse, StreamingResponse

from karaagy.core.process import execute_agy_json, execute_agy_stream
from karaagy.core.prompt import build_agy_prompt
from karaagy.core.registry import ModelRegistry
from karaagy.models.openai import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ErrorDetail,
    ErrorResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["Chat"])


@router.post(
    "/chat/completions",
    response_model=ChatCompletionResponse,
    responses={
        200: {
            "description": "Chat completion response (JSON or SSE stream)",
            "content": {
                "application/json": {},
                "text/event-stream": {},
            },
        },
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def create_chat_completion(request: ChatCompletionRequest) -> Any:
    """Create a chat completion using Antigravity CLI."""
    if not request.messages:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ErrorResponse(
                error=ErrorDetail(
                    message="At least one message is required in 'messages'.",
                    type="invalid_request_error",
                    param="messages",
                    code="missing_required_field",
                )
            ).model_dump(),
        )

    base_model, effort = ModelRegistry.resolve_model_and_effort(request.model, request.effort)
    prompt_text = build_agy_prompt(request.messages)

    if not prompt_text:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ErrorResponse(
                error=ErrorDetail(
                    message="All messages had empty content.",
                    type="invalid_request_error",
                    param="messages",
                    code="empty_content",
                )
            ).model_dump(),
        )

    try:
        if request.stream:
            stream_generator = execute_agy_stream(
                prompt=prompt_text,
                model=base_model,
                effort=effort,
                conversation_id=request.conversation_id,
            )
            return StreamingResponse(
                stream_generator,
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )

        response = await execute_agy_json(
            prompt=prompt_text,
            model=base_model,
            effort=effort,
            conversation_id=request.conversation_id,
        )
        return response

    except RuntimeError as e:
        logger.error("Chat completion runtime error: %s", e)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                error=ErrorDetail(
                    message=str(e),
                    type="api_error",
                    code="execution_failed",
                )
            ).model_dump(),
        )
    except Exception as e:
        logger.exception("Unexpected error in chat completions: %s", e)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                error=ErrorDetail(
                    message=f"Internal server error: {e}",
                    type="api_error",
                    code="internal_error",
                )
            ).model_dump(),
        )
