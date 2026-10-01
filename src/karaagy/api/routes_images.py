"""OpenAI Image Generation endpoints and cached image serving."""

import logging
import mimetypes
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import FileResponse, JSONResponse

from karaagy.config import settings
from karaagy.core.images import generate_images
from karaagy.models.openai import (
    ErrorDetail,
    ErrorResponse,
    ImageGenerationRequest,
    ImagesResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["Images"])


@router.post(
    "/images/generations",
    response_model=ImagesResponse,
    responses={
        200: {"description": "Image generation result"},
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def create_image_generation(request_body: ImageGenerationRequest, request: Request) -> Any:
    """Generate images from text prompt using Antigravity CLI."""
    if not request_body.prompt or not request_body.prompt.strip():
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ErrorResponse(
                error=ErrorDetail(
                    message="Parameter 'prompt' is required and cannot be empty.",
                    type="invalid_request_error",
                    param="prompt",
                    code="missing_required_field",
                )
            ).model_dump(),
        )

    if request_body.n is not None and (request_body.n < 1 or request_body.n > 10):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ErrorResponse(
                error=ErrorDetail(
                    message="Parameter 'n' must be between 1 and 10.",
                    type="invalid_request_error",
                    param="n",
                    code="invalid_parameter_range",
                )
            ).model_dump(),
        )

    base_url = str(request.base_url).rstrip("/")
    try:
        response = await generate_images(request=request_body, base_url=base_url)
        return response
    except ValueError as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ErrorResponse(
                error=ErrorDetail(
                    message=str(e),
                    type="invalid_request_error",
                    param="prompt",
                    code="invalid_request",
                )
            ).model_dump(),
        )
    except Exception as e:
        logger.exception("Error occurred during image generation: %s", e)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                error=ErrorDetail(
                    message=f"Image generation failed: {e}",
                    type="internal_server_error",
                    param=None,
                    code="image_generation_failed",
                )
            ).model_dump(),
        )


@router.get(
    "/images/files/{filename}",
    responses={
        200: {"description": "Cached generated image file"},
        400: {"description": "Invalid filename"},
        404: {"description": "Image not found"},
    },
)
async def get_cached_image(filename: str) -> FileResponse:
    """Retrieve a previously generated cached image file."""
    clean_name = Path(filename).name
    if clean_name != filename or ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename specified.",
        )

    file_path = settings.image_cache_dir / clean_name
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image not found.",
        )

    mime_type, _ = mimetypes.guess_type(str(file_path))
    if not mime_type:
        mime_type = "application/octet-stream"

    return FileResponse(
        path=file_path,
        media_type=mime_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )
