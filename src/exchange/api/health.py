from __future__ import annotations

import platform

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from exchange import __version__
from exchange.cache import RateCache
from exchange.config import Settings
from exchange.providers.base import ExchangeProvider

router = APIRouter(include_in_schema=False)


def _state(request: Request) -> tuple[Settings, ExchangeProvider, RateCache]:
    return request.app.state.settings, request.app.state.provider, request.app.state.cache


async def _readiness(request: Request) -> JSONResponse:
    settings, provider, cache = _state(request)
    provider_status = "UP" if provider.is_configured() else "DOWN"
    cache_status = "DISABLED"
    if settings.cache_enabled:
        cache_status = "UP" if await cache.ping() else "DOWN"

    status = "UP" if provider_status == "UP" and cache_status != "DOWN" else "DOWN"
    if provider_status == "UP" and cache_status == "DOWN":
        status = "DEGRADED"
    body = {
        "status": status,
        "components": {
            "provider": {"status": provider_status},
            "cache": {"status": cache_status},
        },
    }
    return JSONResponse(status_code=200 if provider_status == "UP" else 503, content=body)


@router.get("/health")
async def health(request: Request) -> JSONResponse:
    return await _readiness(request)


@router.get("/health/live")
async def liveness() -> dict[str, str]:
    return {"status": "UP"}


@router.get("/health/ready")
async def readiness(request: Request) -> JSONResponse:
    return await _readiness(request)


@router.get("/actuator/health")
async def actuator_health(request: Request) -> JSONResponse:
    return await _readiness(request)


@router.get("/actuator/health/liveness")
async def actuator_liveness() -> dict[str, str]:
    return {"status": "UP"}


@router.get("/actuator/health/readiness")
async def actuator_readiness(request: Request) -> JSONResponse:
    return await _readiness(request)


@router.get("/info")
async def info(request: Request) -> dict[str, object]:
    settings, provider, _ = _state(request)
    return {
        "service": "exchange",
        "version": __version__,
        "python": platform.python_version(),
        "providerConfigured": provider.is_configured(),
        "cacheEnabled": settings.cache_enabled,
    }
