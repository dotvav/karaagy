"""API router aggregation for Karaagy."""

from fastapi import APIRouter

from karaagy.api.routes_chat import router as chat_router
from karaagy.api.routes_health import router as health_router
from karaagy.api.routes_models import router as models_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(models_router)
api_router.include_router(chat_router)
