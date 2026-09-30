"""Status and system diagnostics endpoints with content negotiation (HTML dashboard and JSON API)."""

import logging
from typing import Any

from fastapi import APIRouter, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse

from karaagy.api.templates import get_logo_svg, render_status_html
from karaagy.config import settings
from karaagy.core.diagnostics import DiagnosticsManager
from karaagy.core.registry import MODEL_ALIASES, ModelRegistry

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Status"])


def resolve_effective_base_url(request: Request) -> str:
    """Resolve public base URL prioritizing headers, configured override, or request base."""
    if settings.public_base_url:
        return str(settings.public_base_url).rstrip("/")

    # Check standard proxy headers
    forwarded_proto = str(request.headers.get("x-forwarded-proto") or request.url.scheme)
    forwarded_host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    if forwarded_host:
        return f"{forwarded_proto}://{forwarded_host}"

    return str(request.base_url).rstrip("/")


@router.get(
    "/",
    summary="Karaagy Status Dashboard & Health Info",
    description="Returns interactive HTML status page for web browsers or JSON payload for API callers.",
)
async def get_root_status(request: Request) -> Any:
    """Content-negotiated root status endpoint."""
    accept_header = request.headers.get("accept", "").lower()
    base_url = resolve_effective_base_url(request)

    version_info = DiagnosticsManager.get_karaagy_version_info()
    agy_version = DiagnosticsManager.get_agy_version()
    metrics = DiagnosticsManager.get_gateway_metrics()
    quota_data = await DiagnosticsManager.get_account_quota()
    models = await ModelRegistry.get_available_models()
    settings_dict = DiagnosticsManager.get_runtime_settings_dict()
    env_vars = DiagnosticsManager.get_sanitized_environment()

    # Browser request -> HTML response
    if "text/html" in accept_header:
        html_content = render_status_html(
            base_url=base_url,
            version_info=version_info,
            agy_version=agy_version,
            metrics=metrics,
            quota_data=quota_data,
            models=models,
            aliases=MODEL_ALIASES,
            settings_dict=settings_dict,
            env_vars=env_vars,
        )
        return HTMLResponse(content=html_content, status_code=200)

    # API request -> JSON response
    return JSONResponse(
        content={
            "service": settings.app_name,
            "status": "online",
            "base_url": base_url,
            "karaagy": version_info,
            "antigravity": {
                "version": agy_version,
                "binary": settings_dict["resolved_agy_bin"],
            },
            "metrics": metrics,
            "quota": quota_data,
            "models": {
                "available": models,
                "default": settings.default_model,
                "default_effort": settings.default_effort,
                "aliases": MODEL_ALIASES,
            },
            "settings": settings_dict,
            "endpoints": {
                "chat_completions": f"{base_url}/v1/chat/completions",
                "models": f"{base_url}/v1/models",
                "health": f"{base_url}/healthz",
                "docs": f"{base_url}/docs",
                "refresh_usage": f"{base_url}/v1/system/refresh-usage",
            },
        },
        status_code=200,
    )


@router.get("/v1/system/status", summary="System Diagnostics API")
async def get_system_status(request: Request) -> Any:
    """Dedicated JSON API endpoint for monitoring and observability."""
    base_url = resolve_effective_base_url(request)
    version_info = DiagnosticsManager.get_karaagy_version_info()
    agy_version = DiagnosticsManager.get_agy_version()
    metrics = DiagnosticsManager.get_gateway_metrics()
    quota_data = await DiagnosticsManager.get_account_quota()
    models = await ModelRegistry.get_available_models()
    settings_dict = DiagnosticsManager.get_runtime_settings_dict()

    return {
        "service": settings.app_name,
        "status": "online",
        "base_url": base_url,
        "karaagy": version_info,
        "antigravity": {
            "version": agy_version,
            "binary": settings_dict["resolved_agy_bin"],
        },
        "metrics": metrics,
        "quota": quota_data,
        "models": {
            "count": len(models),
            "available": models,
            "default": settings.default_model,
        },
    }


@router.post("/v1/system/refresh-usage", summary="Force Refresh Antigravity Quota Cache")
async def refresh_usage_quota() -> Any:
    """Force an immediate refresh of the Antigravity `/usage` quota cache."""
    fresh_quota = await DiagnosticsManager.get_account_quota(force_refresh=True)
    return {
        "status": "refreshed",
        "quota": fresh_quota,
    }


@router.get("/favicon.ico", include_in_schema=False)
@router.get("/favicon.svg", include_in_schema=False)
async def get_favicon() -> Response:
    """Serve the official Karaagy SVG icon for browser favicon requests."""
    svg_content = get_logo_svg()
    return Response(
        content=svg_content,
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=86400"},
    )
