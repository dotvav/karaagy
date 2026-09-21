import base64
import logging
import re
import tempfile
import uuid
from pathlib import Path
from typing import Any

from karaagy.models.openai import ChatCompletionMessage

logger = logging.getLogger(__name__)
TEMP_IMAGE_DIR = Path(tempfile.gettempdir()) / "karaagy_images"


def _process_image_url(url: str, tracked_files: list[Path] | None = None) -> str:
    """Extract clean URL or persist base64 data URI to a local file reference."""
    clean_url = url.strip()
    if clean_url.startswith("data:image/"):
        match = re.match(r"^data:image/([a-zA-Z0-9+.-]+);base64,(.+)$", clean_url, re.DOTALL)
        if match:
            ext = match.group(1).split("+")[0]
            if ext == "jpeg":
                ext = "jpg"
            b64_data = match.group(2).strip()
            try:
                TEMP_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
                img_file = TEMP_IMAGE_DIR / f"img_{uuid.uuid4().hex[:12]}.{ext}"
                img_file.write_bytes(base64.b64decode(b64_data))
                if tracked_files is not None:
                    tracked_files.append(img_file)
                return f"[Attached Image File: {img_file}]"
            except Exception as e:
                logger.warning("Failed to decode base64 image payload: %s", e)
                return "[Attached Image: <base64 image omitted>]"
        return "[Attached Image: <base64 image omitted>]"
    return f"[Attached Image URL: {clean_url}]"


def cleanup_temp_images(files: list[Path] | None) -> None:
    """Safely delete a list of ephemeral image files."""
    if not files:
        return
    for file_path in files:
        try:
            if file_path.exists():
                file_path.unlink(missing_ok=True)
                logger.debug("Cleaned up temp image file: %s", file_path)
        except Exception as e:
            logger.warning("Failed to remove temp image file %s: %s", file_path, e)


def extract_message_text(
    content: str | list[dict[str, Any]] | None,
    tracked_files: list[Path] | None = None,
) -> str:
    """Extract plain text and image references from string or multimodal list content."""
    if not content:
        return ""

    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        text_parts: list[str] = []
        for part in content:
            if isinstance(part, str):
                text_parts.append(part.strip())
            elif isinstance(part, dict):
                part_type = part.get("type", "")
                if part_type == "text":
                    text_val = part.get("text", "")
                    if text_val:
                        text_parts.append(str(text_val).strip())
                elif part_type == "image_url":
                    img_data = part.get("image_url", {})
                    url = img_data.get("url", "") if isinstance(img_data, dict) else str(img_data)
                    if url:
                        text_parts.append(_process_image_url(url, tracked_files))
                elif part_type == "image":
                    url = part.get("url") or part.get("image", "")
                    if url:
                        text_parts.append(_process_image_url(str(url), tracked_files))
                elif "text" in part:
                    text_parts.append(str(part["text"]).strip())
        return "\n".join(text_parts).strip()

    return str(content).strip()


def build_agy_prompt(
    messages: list[ChatCompletionMessage],
    tracked_files: list[Path] | None = None,
) -> str:
    """Format an array of OpenAI chat messages into a coherent prompt for AGY CLI."""
    if not messages:
        return ""

    # Check if single user message without system prompt
    if len(messages) == 1 and messages[0].role == "user":
        return extract_message_text(messages[0].content, tracked_files=tracked_files)

    system_parts: list[str] = []
    conversation_parts: list[str] = []

    for msg in messages:
        role = (msg.role or "user").strip().lower()
        content = extract_message_text(msg.content, tracked_files=tracked_files)

        if not content:
            continue

        if role in ("system", "developer"):
            system_parts.append(content)
        elif role == "user":
            name_prefix = f"User ({msg.name})" if msg.name else "User"
            conversation_parts.append(f"{name_prefix}: {content}")
        elif role == "assistant":
            conversation_parts.append(f"Assistant: {content}")
        elif role in ("tool", "function"):
            name_prefix = f"Tool ({msg.name})" if msg.name else "Tool"
            conversation_parts.append(f"{name_prefix}: {content}")
        else:
            conversation_parts.append(f"{role.capitalize()}: {content}")

    prompt_segments: list[str] = []

    if system_parts:
        prompt_segments.append("### SYSTEM INSTRUCTIONS:\n" + "\n\n".join(system_parts))

    if conversation_parts:
        prompt_segments.append(
            "### CONVERSATION HISTORY & CURRENT PROMPT:\n" + "\n\n".join(conversation_parts)
        )

    return "\n\n".join(prompt_segments)
