"""FastAPI routes for OpenAI Assistants / Threads API."""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import JSONResponse, StreamingResponse

from karaagy.core.threads import ThreadManager
from karaagy.models.openai import ErrorDetail, ErrorResponse
from karaagy.models.threads import (
    CreateRunRequest,
    CreateThreadAndRunRequest,
    CreateThreadMessageRequest,
    CreateThreadRequest,
    RunObject,
    ThreadDeletedResponse,
    ThreadMessage,
    ThreadMessageList,
    ThreadObject,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["Threads"])


@router.post(
    "/threads",
    response_model=ThreadObject,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "Thread created successfully"},
        500: {"model": ErrorResponse},
    },
)
async def create_thread(request: CreateThreadRequest | None = None) -> ThreadObject:
    """Create a new thread."""
    req = request or CreateThreadRequest()
    thread = ThreadManager.create_thread(messages=req.messages, metadata=req.metadata)
    return thread


@router.get(
    "/threads/{thread_id}",
    response_model=ThreadObject,
    responses={
        200: {"description": "Thread details"},
        404: {"model": ErrorResponse},
    },
)
async def get_thread(thread_id: str) -> ThreadObject:
    """Retrieve a thread by ID."""
    thread = ThreadManager.get_thread(thread_id)
    if not thread:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Thread '{thread_id}' not found.",
        )
    return thread


@router.delete(
    "/threads/{thread_id}",
    response_model=ThreadDeletedResponse,
    responses={
        200: {"description": "Thread deleted successfully"},
        404: {"model": ErrorResponse},
    },
)
async def delete_thread(thread_id: str) -> ThreadDeletedResponse:
    """Delete a thread and prune underlying session storage."""
    success = ThreadManager.delete_thread(thread_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Thread '{thread_id}' not found.",
        )
    return ThreadDeletedResponse(id=thread_id, deleted=True)


@router.post(
    "/threads/{thread_id}/messages",
    response_model=ThreadMessage,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "Message appended to thread"},
        404: {"model": ErrorResponse},
    },
)
async def create_thread_message(
    thread_id: str,
    request: CreateThreadMessageRequest,
) -> ThreadMessage:
    """Add a message to a thread."""
    msg = ThreadManager.add_message(thread_id, request)
    if not msg:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Thread '{thread_id}' not found.",
        )
    return msg


@router.get(
    "/threads/{thread_id}/messages",
    response_model=ThreadMessageList,
    responses={
        200: {"description": "List of messages in thread"},
        404: {"model": ErrorResponse},
    },
)
async def list_thread_messages(
    thread_id: str,
    limit: int = Query(default=50, ge=1, le=100),
    order: str = Query(default="desc", pattern="^(asc|desc)$"),
) -> ThreadMessageList:
    """List messages in a thread."""
    msgs = ThreadManager.list_messages(thread_id, limit=limit, order=order)
    if msgs is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Thread '{thread_id}' not found.",
        )
    return msgs


@router.post(
    "/threads/{thread_id}/runs",
    response_model=RunObject,
    responses={
        200: {"description": "Run created and executed"},
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def create_thread_run(
    thread_id: str,
    request: CreateRunRequest | None = None,
) -> Any:
    """Execute a run on a thread."""
    req = request or CreateRunRequest()
    thread = ThreadManager.get_thread(thread_id)
    if not thread:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Thread '{thread_id}' not found.",
        )

    if req.stream:
        stream_gen = ThreadManager.execute_run_stream(thread_id, req)
        return StreamingResponse(
            stream_gen,
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    run_obj, _ = await ThreadManager.execute_run(thread_id, req)
    if run_obj.status == "failed":
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                error=ErrorDetail(
                    message=run_obj.last_error or "Run execution failed",
                    type="api_error",
                    code="run_failed",
                )
            ).model_dump(),
        )
    return run_obj


@router.post(
    "/threads/runs",
    response_model=RunObject,
    responses={
        200: {"description": "Thread created and run executed"},
        500: {"model": ErrorResponse},
    },
)
async def create_thread_and_run(
    request: CreateThreadAndRunRequest,
) -> Any:
    """Create a thread and execute a run in one single API request."""
    thread_req = request.thread or CreateThreadRequest()
    thread = ThreadManager.create_thread(messages=thread_req.messages, metadata=thread_req.metadata)

    run_req = CreateRunRequest(
        assistant_id=request.assistant_id,
        model=request.model,
        instructions=request.instructions,
        additional_instructions=request.additional_instructions,
        additional_messages=request.additional_messages,
        stream=request.stream,
        effort=request.effort,
    )

    if request.stream:
        stream_gen = ThreadManager.execute_run_stream(thread.id, run_req)
        return StreamingResponse(
            stream_gen,
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    run_obj, _ = await ThreadManager.execute_run(thread.id, run_req)
    return run_obj
