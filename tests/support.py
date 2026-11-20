from __future__ import annotations

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import jwt
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from exchange.config import Settings
from exchange.domain.models import ProviderRate

ACCOUNT = UUID("0195ae95-5be7-7dd3-b35d-7a7d87c404fb")
SECRET = "test-secret-with-at-least-32-characters-long"
RATE = ProviderRate(
    sell=Decimal("0.820200"),
    buy=Decimal("0.815000"),
    observed_at=datetime(2026, 1, 1, tzinfo=UTC),
)


def make_settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "jwt_secret": SecretStr(SECRET),
        "exchange_provider_url": "http://provider.test",
        "cache_enabled": False,
        "cache_ttl_seconds": 60,
        "exchange_provider_timeout_seconds": 1.0,
        "exchange_provider_retries": 0,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def make_token(
    settings: Settings,
    *,
    subject: str = str(ACCOUNT),
    roles: list[str] | None = None,
    expires_in: int = 3600,
    secret: str | None = None,
) -> str:
    now = int(time.time())
    payload: dict[str, Any] = {
        "sub": subject,
        "roles": roles or ["ROLE_USER"],
        "iat": now,
        "exp": now + expires_in,
    }
    if settings.jwt_issuer:
        payload["iss"] = settings.jwt_issuer
    if settings.jwt_audience:
        payload["aud"] = settings.jwt_audience
    return jwt.encode(
        payload,
        secret or settings.jwt_secret.get_secret_value(),
        algorithm="HS256",
    )


@asynccontextmanager
async def client_for(application: FastAPI) -> AsyncIterator[AsyncClient]:
    async with LifespanManager(application):
        async with AsyncClient(
            transport=ASGITransport(app=application),
            base_url="http://test",
        ) as http_client:
            yield http_client


class FakeProvider:
    name = "fake"

    def __init__(
        self,
        rate: ProviderRate | None = None,
        error: Exception | None = None,
        configured: bool = True,
    ) -> None:
        self.rate = rate or RATE
        self.error = error
        self.configured = configured
        self.calls: list[tuple[str, str]] = []
        self.closed = False

    async def get_rate(self, source: str, target: str) -> ProviderRate:
        self.calls.append((source, target))
        if self.error is not None:
            raise self.error
        return self.rate

    def is_configured(self) -> bool:
        return self.configured

    async def close(self) -> None:
        self.closed = True


class MemoryCache:
    def __init__(self) -> None:
        self.values: dict[str, ProviderRate] = {}
        self.gets = 0
        self.sets = 0
        self.closed = False
        self.ping_result = True

    async def get(self, key: str) -> ProviderRate | None:
        self.gets += 1
        return self.values.get(key)

    async def set(self, key: str, rate: ProviderRate, ttl_seconds: int) -> None:
        self.sets += 1
        self.values[key] = rate

    async def ping(self) -> bool:
        return self.ping_result

    async def close(self) -> None:
        self.closed = True
