"""Tests for ModelRegistry discovery and alias routing."""

import pytest

from karaagy.core.registry import ModelRegistry


@pytest.mark.asyncio
async def test_resolve_model_aliases() -> None:
    """Test standard OpenAI model aliases resolve to AGY models."""
    assert ModelRegistry.resolve_model("gpt-4o") == "gemini-3.8-flash-high"
    assert ModelRegistry.resolve_model("gpt-3.5-turbo") == "gemini-3.7-flash-low"
    assert ModelRegistry.resolve_model("claude-3-5-sonnet") == "claude-sonnet-4-6"
    assert ModelRegistry.resolve_model("gemini-flash") == "gemini-3.8-flash-high"
    assert ModelRegistry.resolve_model("gemini-pro") == "gemini-3.1-pro-high"
    assert ModelRegistry.resolve_model(None) == "gemini-3.8-flash-high"


@pytest.mark.asyncio
async def test_get_model_cards() -> None:
    """Test generating ModelCard list for /v1/models."""
    ModelRegistry._cached_models = ["gemini-3.8-flash-high", "claude-sonnet-4-6"]
    ModelRegistry._last_fetched_at = 9999999999.0
    cards = await ModelRegistry.get_model_cards()
    card_ids = [c.id for c in cards]
    assert "gemini-3.8-flash-high" in card_ids
    assert "gpt-4o" in card_ids
    assert "claude-sonnet-4-6" in card_ids
    assert all(c.object == "model" for c in cards)
