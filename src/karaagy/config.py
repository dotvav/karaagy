"""Application settings and configuration for Karaagy."""

import shutil
import tempfile
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class KaraagySettings(BaseSettings):
    """Global configuration settings for Karaagy OpenAI-compatible gateway."""

    app_name: str = "Karaagy"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000
    agy_bin: str | None = None
    cache_ttl_seconds: float = 3600.0
    usage_cache_ttl_seconds: float = 600.0
    public_base_url: str | None = None
    default_model: str = "gemini-3.8-flash-high"
    default_effort: str | None = None
    enable_auto_prune_sessions: bool = True
    max_retries: int = 3
    initial_backoff: float = 2.0
    max_concurrent_sessions: int = 4
    antigravity_home: Path = Path.home() / ".gemini" / "antigravity-cli"
    image_cache_dir: Path = Path(tempfile.gettempdir()) / "karaagy_images_cache"
    image_cache_ttl_seconds: float = 86400.0

    model_config = SettingsConfigDict(
        env_prefix="KARAAGY_",
        env_file=".env",
        extra="ignore",
    )

    def resolve_agy_bin(self) -> str:
        """Resolve path to the `agy` binary with container and local fallbacks."""
        if self.agy_bin:
            return self.agy_bin
        which_path = shutil.which("agy")
        if which_path:
            return which_path
        candidates = [
            Path.home() / ".local" / "bin" / "agy",
            Path("/home/karaagy/.local/bin/agy"),
            Path("/home/appuser/.local/bin/agy"),
            Path("/home/golemini/.local/bin/agy"),
            Path("/usr/local/bin/agy"),
            Path("/usr/bin/agy"),
        ]
        for candidate in candidates:
            if candidate.exists() and candidate.is_file():
                return str(candidate)
        return "agy"


settings = KaraagySettings()
