"""OpenAI messages unrolling and prompt synthesis for Antigravity CLI."""

from typing import Any

from karaagy.models.openai import ChatCompletionMessage


def extract_message_text(content: str | list[dict[str, Any]] | None) -> str:
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
                        text_parts.append(f"[Attached Image URL: {url}]")
                elif part_type == "image":
                    url = part.get("url") or part.get("image", "")
                    if url:
                        text_parts.append(f"[Attached Image: {url}]")
                elif "text" in part:
                    text_parts.append(str(part["text"]).strip())
        return "\n".join(text_parts).strip()

    return str(content).strip()


def build_agy_prompt(messages: list[ChatCompletionMessage]) -> str:
    """Format an array of OpenAI chat messages into a coherent prompt for AGY CLI."""
    if not messages:
        return ""

    # Check if single user message without system prompt
    if len(messages) == 1 and messages[0].role == "user":
        return extract_message_text(messages[0].content)

    system_parts: list[str] = []
    conversation_parts: list[str] = []

    for msg in messages:
        role = (msg.role or "user").strip().lower()
        content = extract_message_text(msg.content)

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
