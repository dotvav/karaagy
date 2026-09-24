"""FastAPI application entrypoint for Karaagy OpenAI-compatible gateway."""

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from karaagy.api.router import api_router
from karaagy.config import settings
from karaagy.core.registry import ModelRegistry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager to warm up caches and log startup info."""
    logger.info("Starting %s on %s:%d", settings.app_name, settings.host, settings.port)
    # Warm up model registry and quota caches in background
    asyncio.create_task(ModelRegistry.get_available_models())
    from karaagy.core.diagnostics import DiagnosticsManager

    asyncio.create_task(DiagnosticsManager.get_account_quota())
    yield
    logger.info("Shutting down %s", settings.app_name)


app = FastAPI(
    title=settings.app_name,
    description="OpenAI-compatible REST and SSE API wrapper for Google Antigravity CLI",
    version="0.1.0",
    debug=settings.debug,
    lifespan=lifespan,
)

# Enable CORS for broad web UI / client compatibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
