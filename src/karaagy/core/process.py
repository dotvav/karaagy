"""Asynchronous Antigravity CLI subprocess execution and stream generator."""

import asyncio
import json
import logging
import shutil
import uuid
from collections.abc import AsyncGenerator
from pathlib import Path

from karaagy.config import settings
from karaagy.core.prompt import cleanup_temp_images
from karaagy.core.sanitization import is_retryable_agy_error, sanitize_agy_response
from karaagy.models.agy import AGYJsonResponse, AGYStreamEvent
from karaagy.models.openai import (
    ChatCompletionChoice,
    ChatCompletionChunk,
    ChatCompletionChunkChoice,
    ChatCompletionChunkDelta,
    ChatCompletionMessage,
    ChatCompletionResponse,
    UsageInfo,
)

logger = logging.getLogger(__name__)


def prune_conversation_storage(conversation_id: str | None) -> None:
    """Clean up ephemeral conversation directories and metadata from antigravity storage."""
    if not conversation_id or not settings.enable_auto_prune_sessions:
        return

    base_dir = settings.antigravity_home
    brain_dir = base_dir / "brain" / conversation_id
    convo_file = base_dir / "conversations" / f"{conversation_id}.json"

    try:
        if brain_dir.exists() and brain_dir.is_dir():
            shutil.rmtree(brain_dir, ignore_errors=True)
            logger.debug("Pruned ephemeral brain directory: %s", brain_dir)
        if convo_file.exists() and convo_file.is_file():
            convo_file.unlink(missing_ok=True)
            logger.debug("Pruned ephemeral conversation file: %s", convo_file)
    except Exception as e:
        logger.warning("Failed to prune conversation %s: %s", conversation_id, e)


_concurrency_semaphore: asyncio.Semaphore | None = None


def get_concurrency_semaphore() -> asyncio.Semaphore | None:
    """Lazily initialize and return the global concurrency semaphore."""
    global _concurrency_semaphore
    if settings.max_concurrent_sessions <= 0:
        return None
    if _concurrency_semaphore is None:
        _concurrency_semaphore = asyncio.Semaphore(settings.max_concurrent_sessions)
    return _concurrency_semaphore


def should_pass_effort_flag(model: str, effort: str | None) -> bool:
    """Check if --effort flag should be passed without conflicting with model name."""
    if not effort:
        return False
    model_lower = model.lower()
    if any(model_lower.endswith(f"-{s}") for s in ("low", "medium", "high", "thinking")):
        return False
    return True


async def _execute_agy_json_internal(
    prompt: str,
    model: str,
    effort: str | None = None,
    conversation_id: str | None = None,
    cwd: Path | None = None,
) -> ChatCompletionResponse:
    """Execute non-streaming completion via `agy --output-format json`."""
    agy_bin = settings.resolve_agy_bin()
    working_dir = str(cwd or Path.cwd())
    completion_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    effort_val = effort or settings.default_effort

    cmd = [
        agy_bin,
        "--output-format",
        "json",
        "--dangerously-skip-permissions",
        "--model",
        model,
    ]

    if should_pass_effort_flag(model, effort_val):
        cmd.extend(["--effort", str(effort_val)])

    if conversation_id:
        cmd.extend(["--conversation", conversation_id])

    last_error = ""
    for attempt in range(1, settings.max_retries + 1):
        try:
            logger.info(
                "Running AGY non-streaming (model=%s, attempt=%d/%d)",
                model,
                attempt,
                settings.max_retries,
            )
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=working_dir,
            )
            stdout, stderr = await proc.communicate(input=prompt.encode("utf-8"))
            raw_stdout = stdout.decode("utf-8", errors="replace").strip()
            raw_stderr = stderr.decode("utf-8", errors="replace").strip()

            if proc.returncode != 0:
                combined_err = f"{raw_stderr} {raw_stdout}".strip()
                last_error = combined_err
                logger.warning(
                    "AGY non-streaming failed (code %s): %s", proc.returncode, combined_err
                )
                if attempt < settings.max_retries and is_retryable_agy_error(combined_err):
                    backoff = settings.initial_backoff * (2 ** (attempt - 1))
                    await asyncio.sleep(backoff)
                    continue
                raise RuntimeError(f"AGY CLI error (code {proc.returncode}): {combined_err}")

            # Parse JSON payload
            try:
                data = json.loads(raw_stdout)
                parsed = AGYJsonResponse.model_validate(data)
            except Exception:
                parsed = AGYJsonResponse(response=raw_stdout)

            if parsed.status == "ERROR" or parsed.error:
                err_msg = parsed.error or f"AGY returned status {parsed.status}"
                last_error = err_msg
                logger.warning(
                    "AGY non-streaming returned error status: %s (attempt %d/%d)",
                    err_msg,
                    attempt,
                    settings.max_retries,
                )
                if attempt < settings.max_retries and is_retryable_agy_error(err_msg):
                    backoff = settings.initial_backoff * (2 ** (attempt - 1))
                    await asyncio.sleep(backoff)
                    continue
                raise RuntimeError(f"AGY CLI error: {err_msg}")

            clean_text = sanitize_agy_response(parsed.response)
            if not clean_text:
                last_error = "AGY returned empty text response"
                logger.warning(
                    "AGY returned empty text response (attempt %d/%d)",
                    attempt,
                    settings.max_retries,
                )
                if attempt < settings.max_retries:
                    backoff = settings.initial_backoff * (2 ** (attempt - 1))
                    await asyncio.sleep(backoff)
                    continue
                raise RuntimeError("AGY returned empty response content.")

            usage = UsageInfo()
            if parsed.usage:
                usage = UsageInfo(
                    prompt_tokens=parsed.usage.input_tokens,
                    completion_tokens=parsed.usage.output_tokens,
                    total_tokens=parsed.usage.total_tokens,
                )

            # Auto-prune ephemeral session if stateless request
            if not conversation_id and parsed.conversation_id:
                prune_conversation_storage(parsed.conversation_id)

            return ChatCompletionResponse(
                id=completion_id,
                model=model,
                choices=[
                    ChatCompletionChoice(
                        index=0,
                        message=ChatCompletionMessage(role="assistant", content=clean_text),
                        finish_reason="stop",
                    )
                ],
                usage=usage,
            )

        except Exception as e:
            last_error = str(e)
            if attempt < settings.max_retries and is_retryable_agy_error(last_error):
                backoff = settings.initial_backoff * (2 ** (attempt - 1))
                await asyncio.sleep(backoff)
                continue
            raise

    raise RuntimeError(
        f"Failed to execute AGY command after {settings.max_retries} attempts: {last_error}"
    )


async def execute_agy_json(
    prompt: str,
    model: str,
    effort: str | None = None,
    conversation_id: str | None = None,
    cwd: Path | None = None,
) -> ChatCompletionResponse:
    """Execute non-streaming completion guarded by concurrency semaphore."""
    sem = get_concurrency_semaphore()
    if sem is not None:
        async with sem:
            return await _execute_agy_json_internal(
                prompt=prompt,
                model=model,
                effort=effort,
                conversation_id=conversation_id,
                cwd=cwd,
            )
    return await _execute_agy_json_internal(
        prompt=prompt,
        model=model,
        effort=effort,
        conversation_id=conversation_id,
        cwd=cwd,
    )


async def _execute_agy_stream_internal(
    prompt: str,
    model: str,
    effort: str | None = None,
    conversation_id: str | None = None,
    cwd: Path | None = None,
    temp_files: list[Path] | None = None,
) -> AsyncGenerator[str, None]:
    """Execute streaming completion via `agy --output-format stream-json` and yield SSE events."""
    agy_bin = settings.resolve_agy_bin()
    working_dir = str(cwd or Path.cwd())
    completion_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    effort_val = effort or settings.default_effort

    cmd = [
        agy_bin,
        "--output-format",
        "stream-json",
        "--dangerously-skip-permissions",
        "--model",
        model,
    ]

    if should_pass_effort_flag(model, effort_val):
        cmd.extend(["--effort", str(effort_val)])

    if conversation_id:
        cmd.extend(["--conversation", conversation_id])

    logger.info("Running AGY streaming (model=%s)", model)
    discovered_convo_id: str | None = conversation_id

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=working_dir,
        )

        if proc.stdin is not None:
            proc.stdin.write(prompt.encode("utf-8"))
            await proc.stdin.drain()
            proc.stdin.close()

        if proc.stdout is None:
            raise RuntimeError("Subprocess stdout stream is unavailable")

        # Initial role chunk
        initial_chunk = ChatCompletionChunk(
            id=completion_id,
            model=model,
            choices=[
                ChatCompletionChunkChoice(
                    index=0,
                    delta=ChatCompletionChunkDelta(role="assistant"),
                    finish_reason=None,
                )
            ],
        )
        yield f"data: {initial_chunk.model_dump_json(exclude_none=True)}\n\n"

        while True:
            line = await proc.stdout.readline()
            if not line:
                break

            line_str = line.decode("utf-8", errors="replace").strip()
            if not line_str:
                continue

            try:
                event_data = json.loads(line_str)
                stream_event = AGYStreamEvent.model_validate(event_data)

                if stream_event.conversation_id:
                    discovered_convo_id = stream_event.conversation_id

                if stream_event.event == "step_update" and stream_event.step_update:
                    delta_text = stream_event.step_update.text_delta
                    if delta_text:
                        clean_delta = (
                            sanitize_agy_response(delta_text)
                            if "**Notification" in delta_text
                            else delta_text
                        )
                        chunk = ChatCompletionChunk(
                            id=completion_id,
                            model=model,
                            choices=[
                                ChatCompletionChunkChoice(
                                    index=0,
                                    delta=ChatCompletionChunkDelta(content=clean_delta),
                                    finish_reason=None,
                                )
                            ],
                        )
                        yield f"data: {chunk.model_dump_json(exclude_none=True)}\n\n"

                elif stream_event.event == "result" and stream_event.result:
                    usage = UsageInfo()
                    if stream_event.result.usage:
                        usage = UsageInfo(
                            prompt_tokens=stream_event.result.usage.input_tokens,
                            completion_tokens=stream_event.result.usage.output_tokens,
                            total_tokens=stream_event.result.usage.total_tokens,
                        )
                        from karaagy.core.diagnostics import DiagnosticsManager

                        DiagnosticsManager.record_request_completion(
                            success=True,
                            prompt_tokens=stream_event.result.usage.input_tokens,
                            completion_tokens=stream_event.result.usage.output_tokens,
                        )
                    final_chunk = ChatCompletionChunk(
                        id=completion_id,
                        model=model,
                        choices=[
                            ChatCompletionChunkChoice(
                                index=0,
                                delta=ChatCompletionChunkDelta(),
                                finish_reason="stop",
                            )
                        ],
                        usage=usage,
                    )
                    yield f"data: {final_chunk.model_dump_json(exclude_none=True)}\n\n"

            except Exception as e:
                logger.debug("Non-critical error parsing stream event line: %s", e)

        await proc.wait()

    finally:
        # Ephemeral storage and temp images pruning
        if not conversation_id and discovered_convo_id:
            prune_conversation_storage(discovered_convo_id)
        if temp_files:
            cleanup_temp_images(temp_files)

    yield "data: [DONE]\n\n"


async def execute_agy_stream(
    prompt: str,
    model: str,
    effort: str | None = None,
    conversation_id: str | None = None,
    cwd: Path | None = None,
    temp_files: list[Path] | None = None,
) -> AsyncGenerator[str, None]:
    """Execute streaming completion guarded by concurrency semaphore."""
    sem = get_concurrency_semaphore()
    if sem is not None:
        async with sem:
            async for chunk in _execute_agy_stream_internal(
                prompt=prompt,
                model=model,
                effort=effort,
                conversation_id=conversation_id,
                cwd=cwd,
                temp_files=temp_files,
            ):
                yield chunk
    else:
        async for chunk in _execute_agy_stream_internal(
            prompt=prompt,
            model=model,
            effort=effort,
            conversation_id=conversation_id,
            cwd=cwd,
            temp_files=temp_files,
        ):
            yield chunk
