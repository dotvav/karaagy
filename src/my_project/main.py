"""FastAPI application entrypoint."""

from typing import Any

from fastapi import FastAPI

from src.my_project.config import settings

app = FastAPI(title=settings.app_name, debug=settings.debug)


@app.get("/health")
def health_check() -> dict[str, Any]:
    """Health check endpoint."""
    return {"status": "ok", "app": settings.app_name}


@app.get("/api/v1/ping")
def ping() -> dict[str, str]:
    """Ping endpoint."""
    return {"message": "pong"}
