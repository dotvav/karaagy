"""Tests for process subprocess execution and ephemeral storage pruning."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from karaagy.core.process import execute_agy_json, prune_conversation_storage


def test_prune_conversation_storage(tmp_path: Path) -> None:
    """Test pruning ephemeral directories."""
    brain_dir = tmp_path / "brain" / "conv-1234"
    brain_dir.mkdir(parents=True)
    (brain_dir / "transcript.jsonl").write_text("dummy")

    convo_file = tmp_path / "conversations" / "conv-1234.json"
    convo_file.parent.mkdir(parents=True)
    convo_file.write_text("{}")

    with (
        patch("karaagy.core.process.settings.antigravity_home", tmp_path),
        patch("karaagy.core.process.settings.enable_auto_prune_sessions", True),
    ):
        prune_conversation_storage("conv-1234")

    assert not brain_dir.exists()
    assert not convo_file.exists()


@pytest.mark.asyncio
async def test_execute_agy_json_mocked_proc() -> None:
    """Test execute_agy_json with mocked subprocess."""
    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate.return_value = (
        b'{"conversation_id": "conv-test", "status": "SUCCESS", "response": "Paris", "usage": {"input_tokens": 10, "output_tokens": 2, "total_tokens": 12}}',
        b"",
    )

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        result = await execute_agy_json(
            prompt="Capital of France?",
            model="gemini-3.8-flash-high",
        )
        assert result.choices[0].message.content == "Paris"
        assert result.usage is not None
        assert result.usage.total_tokens == 12
