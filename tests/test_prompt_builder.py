"""Tests for prompt unrolling and synthesis."""

from karaagy.core.prompt import build_agy_prompt
from karaagy.models.openai import ChatCompletionMessage


def test_build_agy_prompt_single_user() -> None:
    """Test single user message returns raw content directly."""
    messages = [ChatCompletionMessage(role="user", content="Hello, world!")]
    result = build_agy_prompt(messages)
    assert result == "Hello, world!"


def test_build_agy_prompt_system_and_user() -> None:
    """Test system and user messages formatting."""
    messages = [
        ChatCompletionMessage(role="system", content="You are a helpful assistant."),
        ChatCompletionMessage(role="user", content="What is 2+2?"),
    ]
    result = build_agy_prompt(messages)
    assert "### SYSTEM INSTRUCTIONS:" in result
    assert "You are a helpful assistant." in result
    assert "### CONVERSATION HISTORY & CURRENT PROMPT:" in result
    assert "User: What is 2+2?" in result


def test_build_agy_prompt_multi_turn() -> None:
    """Test multi-turn user and assistant dialogue."""
    messages = [
        ChatCompletionMessage(role="system", content="Be concise."),
        ChatCompletionMessage(role="user", content="Hi", name="Alice"),
        ChatCompletionMessage(role="assistant", content="Hello Alice."),
        ChatCompletionMessage(role="user", content="How are you?"),
    ]
    result = build_agy_prompt(messages)
    assert "User (Alice): Hi" in result
    assert "Assistant: Hello Alice." in result
    assert "User: How are you?" in result


def test_build_agy_prompt_empty() -> None:
    """Test handling of empty messages list."""
    assert build_agy_prompt([]) == ""
