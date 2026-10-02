"""Thread management and persistence for OpenAI Assistants / Threads API."""

import asyncio
import json
import logging
import re
import time
import uuid
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from karaagy.config import settings
from karaagy.core.process import (
    _execute_agy_json_internal,
    _execute_agy_stream_internal,
    prune_conversation_storage,
)
from karaagy.core.prompt import cleanup_temp_images
from karaagy.core.registry import ModelRegistry
from karaagy.models.openai import UsageInfo
from karaagy.models.threads import (
    CreateRunRequest,
    CreateThreadMessageRequest,
    RunObject,
    ThreadMessage,
    ThreadMessageList,
    ThreadObject,
)

logger = logging.getLogger(__name__)


class ThreadState(BaseModel):
    """Internal persisted representation of an OpenAI Thread."""

    id: str
    created_at: int = Field(default_factory=lambda: int(time.time()))
    last_active_at: int = Field(default_factory=lambda: int(time.time()))
    conversation_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    messages: list[ThreadMessage] = Field(default_factory=list)


class ThreadManager:
    """Manager for persistent threads backed by Antigravity conversation sessions."""

    @classmethod
    def _get_storage_dir(cls) -> Path:
        storage_dir = Path(settings.threads_dir)
        storage_dir.mkdir(parents=True, exist_ok=True)
        return storage_dir

    @classmethod
    def _get_thread_file(cls, thread_id: str) -> Path:
        clean_id = Path(thread_id).name
        if clean_id != thread_id or not re.match(r"^[a-zA-Z0-9_-]+$", thread_id):
            raise ValueError(f"Invalid thread ID format: '{thread_id}'.")
        return cls._get_storage_dir() / f"{clean_id}.json"

    @classmethod
    def _save_state(cls, state: ThreadState) -> None:
        file_path = cls._get_thread_file(state.id)
        file_path.write_text(state.model_dump_json(indent=2), encoding="utf-8")

    @classmethod
    def _load_state(cls, thread_id: str) -> ThreadState | None:
        try:
            file_path = cls._get_thread_file(thread_id)
        except ValueError:
            return None
        if not file_path.exists() or not file_path.is_file():
            return None
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            return ThreadState(**data)
        except Exception as e:
            logger.warning("Failed to parse thread file for %s: %s", thread_id, e)
            return None

    @classmethod
    def create_thread(
        cls,
        messages: list[CreateThreadMessageRequest] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ThreadObject:
        """Create a new persistent thread and associated AGY conversation."""
        thread_id = f"thread_{uuid.uuid4().hex[:20]}"
        convo_id: str | None = (
            str(metadata["conversation_id"])
            if (metadata and "conversation_id" in metadata)
            else None
        )
        state = ThreadState(
            id=thread_id,
            conversation_id=convo_id,
            metadata=metadata or {},
            messages=[],
        )

        if messages:
            for msg_req in messages:
                msg_id = f"msg_{uuid.uuid4().hex[:20]}"
                content_list: list[dict[str, Any]]
                if isinstance(msg_req.content, str):
                    content_list = [{"type": "text", "text": {"value": msg_req.content}}]
                elif isinstance(msg_req.content, list):
                    content_list = msg_req.content
                else:
                    content_list = [{"type": "text", "text": {"value": str(msg_req.content)}}]

                thread_msg = ThreadMessage(
                    id=msg_id,
                    thread_id=thread_id,
                    role=msg_req.role,
                    content=content_list,
                    metadata=msg_req.metadata or {},
                )
                state.messages.append(thread_msg)

        cls._save_state(state)
        logger.info("Created thread %s (initial convo_id=%s)", thread_id, convo_id)
        return ThreadObject(
            id=state.id,
            created_at=state.created_at,
            metadata=state.metadata,
            conversation_id=state.conversation_id,
        )

    @classmethod
    def get_thread(cls, thread_id: str) -> ThreadObject | None:
        """Fetch a thread by ID."""
        state = cls._load_state(thread_id)
        if not state:
            return None
        return ThreadObject(
            id=state.id,
            created_at=state.created_at,
            metadata=state.metadata,
            conversation_id=state.conversation_id,
        )

    @classmethod
    def delete_thread(cls, thread_id: str) -> bool:
        """Delete a thread and purge its underlying AGY storage."""
        state = cls._load_state(thread_id)
        if not state:
            return False

        if state.conversation_id:
            prune_conversation_storage(state.conversation_id)
        file_path = cls._get_thread_file(thread_id)
        try:
            file_path.unlink(missing_ok=True)
            logger.info(
                "Deleted thread %s and pruned AGY storage %s", thread_id, state.conversation_id
            )
            return True
        except Exception as e:
            logger.error("Failed to delete thread file %s: %s", file_path, e)
            return False

    @classmethod
    def add_message(cls, thread_id: str, req: CreateThreadMessageRequest) -> ThreadMessage | None:
        """Append a message to a thread."""
        state = cls._load_state(thread_id)
        if not state:
            return None

        msg_id = f"msg_{uuid.uuid4().hex[:20]}"
        content_list: list[dict[str, Any]]
        if isinstance(req.content, str):
            content_list = [{"type": "text", "text": {"value": req.content}}]
        elif isinstance(req.content, list):
            content_list = req.content
        else:
            content_list = [{"type": "text", "text": {"value": str(req.content)}}]

        thread_msg = ThreadMessage(
            id=msg_id,
            thread_id=thread_id,
            role=req.role,
            content=content_list,
            metadata=req.metadata or {},
        )
        state.messages.append(thread_msg)
        state.last_active_at = int(time.time())
        cls._save_state(state)
        return thread_msg

    @classmethod
    def list_messages(
        cls,
        thread_id: str,
        limit: int = 50,
        order: str = "desc",
    ) -> ThreadMessageList | None:
        """List messages in a thread."""
        state = cls._load_state(thread_id)
        if not state:
            return None

        msgs = list(state.messages)
        if order.lower() == "desc":
            msgs = msgs[::-1]

        paginated = msgs[:limit]
        first_id = paginated[0].id if paginated else None
        last_id = paginated[-1].id if paginated else None

        return ThreadMessageList(
            data=paginated,
            first_id=first_id,
            last_id=last_id,
            has_more=len(msgs) > limit,
        )

    @classmethod
    def _build_run_prompt(
        cls,
        state: ThreadState,
        run_req: CreateRunRequest,
        tracked_images: list[Path],
    ) -> str:
        """Build the delta prompt to send to AGY for this run."""
        prompt_parts: list[str] = []

        # 1. System instructions if provided
        instructions = run_req.instructions or run_req.additional_instructions
        if instructions:
            prompt_parts.append(f"### INSTRUCTIONS:\n{instructions.strip()}")

        # 2. Extract messages since last assistant turn, or last user message
        # If additional_messages are provided in the run request, append them first
        if run_req.additional_messages:
            for msg_req in run_req.additional_messages:
                cls.add_message(state.id, msg_req)
            state = cls._load_state(state.id) or state

        # Find unsent user messages (messages since last assistant turn)
        unsent_messages: list[ThreadMessage] = []
        for msg in reversed(state.messages):
            if msg.role == "assistant":
                break
            unsent_messages.insert(0, msg)

        # If no unsent user messages found (e.g. run called immediately), take the last message
        if not unsent_messages and state.messages:
            unsent_messages = [state.messages[-1]]

        user_content_parts: list[str] = []
        for msg in unsent_messages:
            for part in msg.content:
                part_type = part.get("type", "")
                if part_type == "text":
                    text_obj = part.get("text", {})
                    val = text_obj.get("value", "") if isinstance(text_obj, dict) else str(text_obj)
                    if val:
                        user_content_parts.append(val.strip())
                elif part_type in ("image_url", "image_file"):
                    # Process image attachment
                    from karaagy.core.prompt import _process_image_url

                    img_data = part.get("image_url", {})
                    url = img_data.get("url", "") if isinstance(img_data, dict) else str(img_data)
                    if url:
                        user_content_parts.append(_process_image_url(url, tracked_images))
                elif "text" in part:
                    user_content_parts.append(str(part["text"]).strip())

        if user_content_parts:
            prompt_parts.append("\n".join(user_content_parts))

        return "\n\n".join(prompt_parts).strip()

    @classmethod
    async def execute_run(
        cls,
        thread_id: str,
        run_req: CreateRunRequest,
    ) -> tuple[RunObject, ThreadMessage | None]:
        """Execute a synchronous run on a thread."""
        state = cls._load_state(thread_id)
        if not state:
            raise ValueError(f"Thread {thread_id} not found")

        model_name = run_req.model or settings.default_model
        base_model, effort = ModelRegistry.resolve_model_and_effort(model_name, run_req.effort)
        run_id = f"run_{uuid.uuid4().hex[:20]}"
        tracked_images: list[Path] = []

        prompt_text = cls._build_run_prompt(state, run_req, tracked_images)
        if not prompt_text:
            prompt_text = "Continue."

        try:
            logger.info(
                "Executing thread %s run %s (model=%s, convo=%s)",
                thread_id,
                run_id,
                base_model,
                state.conversation_id,
            )
            completion = await _execute_agy_json_internal(
                prompt=prompt_text,
                model=base_model,
                effort=effort,
                conversation_id=state.conversation_id,
            )

            # Capture and persist actual AGY conversation ID for future turns
            if completion.conversation_id and completion.conversation_id != state.conversation_id:
                state.conversation_id = completion.conversation_id
                cls._save_state(state)

            assistant_text = ""
            if completion.choices and completion.choices[0].message:
                raw_c = completion.choices[0].message.content
                assistant_text = raw_c if isinstance(raw_c, str) else str(raw_c or "")

            # Append assistant response message to thread
            asst_msg_req = CreateThreadMessageRequest(
                role="assistant",
                content=assistant_text,
            )
            asst_msg = cls.add_message(thread_id, asst_msg_req)

            run_obj = RunObject(
                id=run_id,
                thread_id=thread_id,
                assistant_id=run_req.assistant_id,
                status="completed",
                model=base_model,
                instructions=run_req.instructions,
                usage=completion.usage or UsageInfo(),
            )
            return run_obj, asst_msg

        except Exception as e:
            logger.exception("Thread run %s failed: %s", run_id, e)
            run_obj = RunObject(
                id=run_id,
                thread_id=thread_id,
                assistant_id=run_req.assistant_id,
                status="failed",
                model=base_model,
                instructions=run_req.instructions,
                last_error="Internal server error during run execution.",
            )
            return run_obj, None
        finally:
            cleanup_temp_images(tracked_images)

    @classmethod
    async def execute_run_stream(
        cls,
        thread_id: str,
        run_req: CreateRunRequest,
    ) -> AsyncGenerator[str, None]:
        """Execute a streaming run on a thread yielding SSE events."""
        state = cls._load_state(thread_id)
        if not state:
            raise ValueError(f"Thread {thread_id} not found")

        model_name = run_req.model or settings.default_model
        base_model, effort = ModelRegistry.resolve_model_and_effort(model_name, run_req.effort)
        run_id = f"run_{uuid.uuid4().hex[:20]}"
        tracked_images: list[Path] = []

        prompt_text = cls._build_run_prompt(state, run_req, tracked_images)
        if not prompt_text:
            prompt_text = "Continue."

        accumulated_text: list[str] = []
        discovered_convo_id: str | None = state.conversation_id

        try:
            logger.info(
                "Executing thread %s streaming run %s (model=%s, convo=%s)",
                thread_id,
                run_id,
                base_model,
                state.conversation_id,
            )
            async for chunk_str in _execute_agy_stream_internal(
                prompt=prompt_text,
                model=base_model,
                effort=effort,
                conversation_id=state.conversation_id,
                temp_files=tracked_images,
            ):
                # Parse delta if needed to accumulate text for saving
                if chunk_str.startswith("data: ") and not chunk_str.startswith("data: [DONE]"):
                    try:
                        raw_json = chunk_str[6:].strip()
                        cdata = json.loads(raw_json)
                        if "conversation_id" in cdata and cdata["conversation_id"]:
                            discovered_convo_id = cdata["conversation_id"]
                        choices = cdata.get("choices", [])
                        if choices and "delta" in choices[0]:
                            delta_content = choices[0]["delta"].get("content")
                            if delta_content:
                                accumulated_text.append(delta_content)
                    except Exception:
                        pass
                yield chunk_str

            # Save completed assistant message
            full_assistant_text = "".join(accumulated_text).strip()
            if full_assistant_text:
                asst_msg_req = CreateThreadMessageRequest(
                    role="assistant",
                    content=full_assistant_text,
                )
                cls.add_message(thread_id, asst_msg_req)

            # Persist actual AGY conversation ID
            if discovered_convo_id and discovered_convo_id != state.conversation_id:
                state.conversation_id = discovered_convo_id
                cls._save_state(state)

        finally:
            cleanup_temp_images(tracked_images)

    @classmethod
    def prune_expired_threads(cls) -> int:
        """Prune threads inactive for longer than thread_ttl_seconds."""
        now = int(time.time())
        ttl = settings.thread_ttl_seconds
        storage_dir = cls._get_storage_dir()
        if not storage_dir.exists():
            return 0

        pruned_count = 0
        for json_file in storage_dir.glob("thread_*.json"):
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                last_active = data.get("last_active_at", data.get("created_at", 0))
                if now - last_active > ttl:
                    thread_id = data.get("id") or json_file.stem
                    convo_id = data.get("conversation_id")
                    if convo_id:
                        prune_conversation_storage(convo_id)
                    json_file.unlink(missing_ok=True)
                    pruned_count += 1
                    logger.info("Pruned expired thread %s (inactive for > %ds)", thread_id, ttl)
            except Exception as e:
                logger.warning("Error inspecting thread file %s for pruning: %s", json_file, e)

        return pruned_count


async def periodic_thread_cleanup_loop(interval_seconds: float = 3600.0) -> None:
    """Periodic background task to prune expired threads."""
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            pruned = ThreadManager.prune_expired_threads()
            if pruned > 0:
                logger.info("Periodic thread cleanup: removed %d expired threads", pruned)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("Error in periodic thread cleanup loop: %s", e)
