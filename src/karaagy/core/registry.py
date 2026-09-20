"""Dynamic Model Registry and Alias Router for Antigravity models."""

import asyncio
import logging
import time

from karaagy.config import settings
from karaagy.models.openai import ModelCard

logger = logging.getLogger(__name__)

# Fallback alias table mapping common client model requests to AGY candidate models
MODEL_ALIASES: dict[str, str] = {
    "gpt-4o": "gemini-3.8-flash-high",
    "gpt-4o-mini": "gemini-3.7-flash-low",
    "gpt-4": "gemini-3.8-flash-high",
    "gpt-4-turbo": "gemini-3.8-flash-high",
    "gpt-3.5-turbo": "gemini-3.7-flash-low",
    "claude-3-5-sonnet": "claude-sonnet-4-6",
    "claude-3-7-sonnet": "claude-sonnet-4-6",
    "claude-sonnet": "claude-sonnet-4-6",
    "claude-3-opus": "claude-opus-4-6-thinking",
    "claude-opus": "claude-opus-4-6-thinking",
    "gemini-flash": "gemini-3.8-flash-high",
    "gemini-pro": "gemini-3.1-pro-high",
    "default": "gemini-3.8-flash-high",
}

# Static fallback candidates if CLI discovery is unavailable
DEFAULT_MODELS: list[str] = [
    "gemini-3.8-flash-high",
    "gemini-3.8-flash-medium",
    "gemini-3.8-flash-low",
    "gemini-3.7-flash-high",
    "gemini-3.7-flash-medium",
    "gemini-3.7-flash-low",
    "gemini-3.6-flash-high",
    "gemini-3.6-flash-medium",
    "gemini-3.6-flash-low",
    "gemini-3.1-pro-high",
    "gemini-3.1-pro-low",
    "claude-sonnet-4-6",
    "claude-opus-4-6-thinking",
    "gpt-oss-120b-medium",
]


class ModelRegistry:
    """Manages dynamic model discovery, alias resolution, and caching."""

    _cached_models: list[str] = []
    _last_fetched_at: float = 0.0

    @classmethod
    async def get_available_models(cls, force_refresh: bool = False) -> list[str]:
        """Fetch available models via `agy models` CLI or return cached list."""
        now = time.time()
        if (
            not force_refresh
            and cls._cached_models
            and (now - cls._last_fetched_at < settings.cache_ttl_seconds)
        ):
            return cls._cached_models

        agy_bin = settings.resolve_agy_bin()
        try:
            proc = await asyncio.create_subprocess_exec(
                agy_bin,
                "models",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode == 0 and stdout:
                lines = stdout.decode("utf-8", errors="replace").splitlines()
                discovered: list[str] = []
                for line in lines:
                    stripped = line.strip()
                    if not stripped or stripped.startswith("⠋") or stripped.startswith("⠙"):
                        continue
                    parts = stripped.split()
                    if parts:
                        model_name = parts[0]
                        if model_name not in discovered:
                            discovered.append(model_name)
                if discovered:
                    cls._cached_models = discovered
                    cls._last_fetched_at = now
                    logger.info("Discovered %d models from `agy models`", len(discovered))
                    return cls._cached_models
        except Exception as e:
            logger.warning("Failed to discover models via `agy models`: %s", e)

        if not cls._cached_models:
            cls._cached_models = list(DEFAULT_MODELS)
            cls._last_fetched_at = now

        return cls._cached_models

    @classmethod
    def resolve_model(cls, requested_model: str | None) -> str:
        """Resolve an incoming model string or alias to a valid AGY model name."""
        if not requested_model:
            return str(settings.default_model)

        normalized = requested_model.strip().lower()

        # Direct match in alias map
        if normalized in MODEL_ALIASES:
            return MODEL_ALIASES[normalized]

        # Check if requested model exists in cached models
        for m in cls._cached_models:
            if m.lower() == normalized:
                return str(m)

        # Check in default models
        for m in DEFAULT_MODELS:
            if m.lower() == normalized:
                return str(m)

        # If not found, return as-is or fallback to default
        return str(requested_model or settings.default_model)

    @classmethod
    async def get_model_cards(cls) -> list[ModelCard]:
        """Return list of ModelCard objects for `/v1/models` endpoint."""
        models = await cls.get_available_models()
        cards: list[ModelCard] = [
            ModelCard(id=m, object="model", created=1700000000, owned_by="antigravity")
            for m in models
        ]
        # Include popular aliases as virtual models
        for alias in [
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-3.5-turbo",
            "claude-3-5-sonnet",
            "gemini-flash",
            "gemini-pro",
        ]:
            if alias not in [c.id for c in cards]:
                cards.append(
                    ModelCard(id=alias, object="model", created=1700000000, owned_by="antigravity")
                )
        return cards
