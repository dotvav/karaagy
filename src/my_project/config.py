"""Application settings and configuration."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Global application settings."""

    app_name: str = "My Project"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000

    model_config = SettingsConfigDict(env_prefix="APP_", env_file=".env")


settings = Settings()
