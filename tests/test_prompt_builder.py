"""Tests for prompt unrolling and synthesis."""

from pathlib import Path

from karaagy.core.prompt import build_agy_prompt, cleanup_temp_images
from karaagy.models.openai import (
    ChatCompletionMessage,
    ResponseFormat,
    ResponseFormatJsonSchema,
)


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


def test_build_agy_prompt_multimodal_list() -> None:
    """Test handling of multimodal content parts (text and image_url)."""
    messages = [
        ChatCompletionMessage(
            role="user",
            content=[
                {"type": "text", "text": "Check this item:"},
                {
                    "type": "image_url",
                    "image_url": {"url": "https://example.com/item.jpg"},
                },
            ],
        )
    ]
    result = build_agy_prompt(messages)
    assert "Check this item:" in result
    assert "[Attached Image URL: https://example.com/item.jpg]" in result


def test_build_agy_prompt_base64_image() -> None:
    """Test handling of base64 data URIs saved as local image files and cleanup."""
    dummy_png = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    messages = [
        ChatCompletionMessage(
            role="user",
            content=[
                {"type": "text", "text": "Inspect image:"},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{dummy_png}"},
                },
            ],
        )
    ]
    tracked: list[Path] = []
    result = build_agy_prompt(messages, tracked_files=tracked)
    assert "Inspect image:" in result
    assert "[Attached Image File:" in result
    assert ".png]" in result
    assert len(tracked) == 1
    assert tracked[0].exists()

    # Test cleanup
    cleanup_temp_images(tracked)
    assert not tracked[0].exists()


def test_build_agy_prompt_single_user_json_object() -> None:
    """Test single user message with json_object response format bypasses short-circuit."""
    messages = [ChatCompletionMessage(role="user", content="Extract users")]
    result = build_agy_prompt(messages, response_format={"type": "json_object"})

    # Single-user raw short circuit must NOT happen
    assert result != "Extract users"
    assert "### SYSTEM INSTRUCTIONS:" in result
    assert (
        "CRITICAL FORMAT REQUIREMENT: You MUST respond ONLY with a raw, valid JSON payload."
        in result
    )
    assert "Do NOT wrap the JSON output in Markdown code fences" in result
    assert "STRICT TOOL EXECUTION POLICY: Do NOT execute any tools or background tasks" in result
    assert "The JSON output MUST be a valid, well-formed JSON object or array." in result
    assert "### CONVERSATION HISTORY & CURRENT PROMPT:" in result
    assert "User: Extract users" in result


def test_build_agy_prompt_single_user_json_schema_dict() -> None:
    """Test single user message with json_schema dict injects schema and anti-tool policy."""
    schema_payload = {
        "type": "json_schema",
        "json_schema": {
            "name": "nutrients",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {"calories": {"type": "number"}},
                "required": ["calories"],
            },
        },
    }
    messages = [ChatCompletionMessage(role="user", content="Extract nutrient data")]
    result = build_agy_prompt(messages, response_format=schema_payload)

    assert "### SYSTEM INSTRUCTIONS:" in result
    assert "The JSON output MUST strictly conform to the following JSON Schema:" in result
    assert '"calories": {\n      "type": "number"\n    }' in result
    assert "STRICT TOOL EXECUTION POLICY: Do NOT execute any tools or background tasks" in result
    assert "### CONVERSATION HISTORY & CURRENT PROMPT:" in result
    assert "User: Extract nutrient data" in result


def test_build_agy_prompt_pydantic_response_format() -> None:
    """Test ResponseFormat Pydantic instance handling for json_schema and json_object."""
    rf_schema = ResponseFormat(
        type="json_schema",
        json_schema=ResponseFormatJsonSchema(
            name="sentiment_eval",
            strict=True,
            schema={"type": "object", "properties": {"sentiment": {"type": "string"}}},
        ),
    )
    messages = [ChatCompletionMessage(role="user", content="Evaluate sentiment")]
    result = build_agy_prompt(messages, response_format=rf_schema)

    assert "### SYSTEM INSTRUCTIONS:" in result
    assert '"sentiment": {\n      "type": "string"\n    }' in result
    assert "STRICT TOOL EXECUTION POLICY:" in result
    assert "User: Evaluate sentiment" in result

    # Test Pydantic ResponseFormat with json_object
    rf_obj = ResponseFormat(type="json_object")
    result_obj = build_agy_prompt(messages, response_format=rf_obj)
    assert "### SYSTEM INSTRUCTIONS:" in result_obj
    assert "The JSON output MUST be a valid, well-formed JSON object or array." in result_obj


def test_build_agy_prompt_multiturn_multimodal_json_schema() -> None:
    """Test multi-turn dialogue with system message, image, and json_schema format."""
    messages = [
        ChatCompletionMessage(role="system", content="You are a certified nutritionist."),
        ChatCompletionMessage(
            role="user",
            content=[
                {"type": "text", "text": "Analyze this meal:"},
                {
                    "type": "image_url",
                    "image_url": {"url": "https://example.com/meal.jpg"},
                },
            ],
        ),
        ChatCompletionMessage(role="assistant", content="Looks like a bowl of pasta."),
        ChatCompletionMessage(role="user", content="Provide precise macronutrients."),
    ]
    rf = {
        "type": "json_schema",
        "schema": {
            "type": "object",
            "properties": {
                "protein_g": {"type": "number"},
                "carbs_g": {"type": "number"},
            },
            "required": ["protein_g", "carbs_g"],
        },
    }
    result = build_agy_prompt(messages, response_format=rf)

    assert "### SYSTEM INSTRUCTIONS:" in result
    assert "You are a certified nutritionist." in result
    assert "The JSON output MUST strictly conform to the following JSON Schema:" in result
    assert '"protein_g": {\n      "type": "number"\n    }' in result
    assert "STRICT TOOL EXECUTION POLICY:" in result

    assert "### CONVERSATION HISTORY & CURRENT PROMPT:" in result
    assert "User: Analyze this meal:\n[Attached Image URL: https://example.com/meal.jpg]" in result
    assert "Assistant: Looks like a bowl of pasta." in result
    assert "User: Provide precise macronutrients." in result


def test_build_agy_prompt_non_json_preserves_short_circuit() -> None:
    """Test non-JSON formats (text, None) preserve single-user direct pass-through short-circuit."""
    messages = [ChatCompletionMessage(role="user", content="Tell me a joke")]

    # response_format=None
    assert build_agy_prompt(messages, response_format=None) == "Tell me a joke"

    # response_format={"type": "text"}
    assert build_agy_prompt(messages, response_format={"type": "text"}) == "Tell me a joke"

    # response_format=ResponseFormat(type="text")
    assert (
        build_agy_prompt(messages, response_format=ResponseFormat(type="text")) == "Tell me a joke"
    )
