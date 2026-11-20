from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from exchange import __version__
from exchange.api import health, routes
from exchange.api.auth import JwtAuthenticator
from exchange.api.errors import install_error_handlers
from exchange.cache import RateCache, build_cache
from exchange.config import Settings, get_settings
from exchange.observability import (
    MetricsMiddleware,
    RequestIdMiddleware,
    configure_logging,
    install_metrics,
)
from exchange.providers.base import ExchangeProvider
from exchange.providers.http import HttpExchangeProvider
from exchange.services.exchange_service import ExchangeService


def create_app(
    settings: Settings | None = None,
    *,
    provider: ExchangeProvider | None = None,
    cache: RateCache | None = None,
) -> FastAPI:
    resolved = settings or get_settings()
    configure_logging(resolved.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = resolved
        app.state.authenticator = JwtAuthenticator(resolved)
        app.state.provider = provider or HttpExchangeProvider(resolved)
        app.state.cache = cache or build_cache(resolved)
        app.state.exchange_service = ExchangeService(
            resolved,
            app.state.provider,
            app.state.cache,
        )
        try:
            yield
        finally:
            await app.state.provider.close()
            await app.state.cache.close()

    app = FastAPI(
        title="Exchange API",
        version=__version__,
        summary="Currency conversion for the Microsserv52 platform.",
        lifespan=lifespan,
    )
    app.add_middleware(MetricsMiddleware)
    app.add_middleware(RequestIdMiddleware)
    install_error_handlers(app)
    install_metrics(app)
    app.include_router(health.router)
    app.include_router(routes.router)
    return app


app = create_app()
