from __future__ import annotations

import os

os.environ.setdefault("JWT_SECRET", "test-secret-with-at-least-32-characters-long")
os.environ.setdefault("EXCHANGE_PROVIDER_URL", "http://provider.test")

from collections.abc import AsyncIterator  # noqa: E402

import pytest  # noqa: E402
from asgi_lifespan import LifespanManager  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from exchange.cache import RateCache  # noqa: E402
from exchange.config import Settings  # noqa: E402
from exchange.main import create_app  # noqa: E402
from exchange.providers.base import ExchangeProvider  # noqa: E402
from tests.support import FakeProvider, MemoryCache, make_settings, make_token  # noqa: E402


@pytest.fixture
def settings() -> Settings:
    return make_settings()


@pytest.fixture
def provider() -> FakeProvider:
    return FakeProvider()


@pytest.fixture
def cache() -> MemoryCache:
    return MemoryCache()


@pytest.fixture
def application(
    settings: Settings,
    provider: ExchangeProvider,
    cache: RateCache,
):
    return create_app(settings, provider=provider, cache=cache)


@pytest.fixture
async def client(application) -> AsyncIterator[AsyncClient]:
    async with LifespanManager(application):
        async with AsyncClient(
            transport=ASGITransport(app=application),
            base_url="http://test",
        ) as http_client:
            yield http_client


@pytest.fixture
def auth_headers(settings: Settings) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(settings)}"}
