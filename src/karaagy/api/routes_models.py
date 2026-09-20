"""OpenAI Models endpoints."""

from fastapi import APIRouter, HTTPException, status

from karaagy.core.registry import ModelRegistry
from karaagy.models.openai import ModelCard, ModelList

router = APIRouter(prefix="/v1", tags=["Models"])


@router.get("/models", response_model=ModelList)
async def list_models() -> ModelList:
    """List available Antigravity models and supported aliases."""
    cards = await ModelRegistry.get_model_cards()
    return ModelList(object="list", data=cards)


@router.get("/models/{model_id:path}", response_model=ModelCard)
async def get_model(model_id: str) -> ModelCard:
    """Retrieve details for a specific model."""
    cards = await ModelRegistry.get_model_cards()
    for card in cards:
        if card.id == model_id:
            return card
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Model '{model_id}' does not exist.",
    )
