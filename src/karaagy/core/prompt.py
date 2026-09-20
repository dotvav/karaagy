"""OpenAI messages unrolling and prompt synthesis for Antigravity CLI."""

from karaagy.models.openai import ChatCompletionMessage


def build_agy_prompt(messages: list[ChatCompletionMessage]) -> str:
    """Format an array of OpenAI chat messages into a coherent prompt for AGY CLI."""
    if not messages:
        return ""

    # Check if single user message without system prompt
    if len(messages) == 1 and messages[0].role == "user":
        return messages[0].content or ""

    system_parts: list[str] = []
    conversation_parts: list[str] = []

    for msg in messages:
        role = (msg.role or "user").strip().lower()
        content = (msg.content or "").strip()

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
