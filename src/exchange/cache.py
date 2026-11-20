from __future__ import annotations

import json
import logging
from decimal import Decimal, InvalidOperation
from typing import Protocol

from pydantic import ValidationError
from redis.asyncio import Redis
from redis.exceptions import RedisError

from exchange.config import Settings
from exchange.domain.models import ProviderRate
from exchange.observability import CACHE_EVENTS

LOGGER = logging.getLogger(__name__)


class RateCache(Protocol):
    async def get(self, key: str) -> ProviderRate | None: ...

    async def set(self, key: str, rate: ProviderRate, ttl_seconds: int) -> None: ...

    async def ping(self) -> bool: ...

    async def close(self) -> None: ...


class NullRateCache:
    async def get(self, key: str) -> ProviderRate | None:
        return None

    async def set(self, key: str, rate: ProviderRate, ttl_seconds: int) -> None:
        return None

    async def ping(self) -> bool:
        return True

    async def close(self) -> None:
        return None


class RedisRateCache:
    """TTL cache that degrades to a miss when Redis is unavailable."""

    def __init__(self, redis: Redis, ttl_seconds: int) -> None:
        self._redis = redis
        self._ttl_seconds = ttl_seconds

    async def get(self, key: str) -> ProviderRate | None:
        try:
            payload = await self._redis.get(key)
        except RedisError as error:
            CACHE_EVENTS.labels(event="error").inc()
            LOGGER.warning("Cache get failed: %s", type(error).__name__)
            return None
        if payload is None:
            CACHE_EVENTS.labels(event="miss").inc()
            return None
        try:
            decoded = json.loads(payload)
            rate = ProviderRate.model_validate(
                {
                    "sell": Decimal(decoded["sell"]),
                    "buy": Decimal(decoded["buy"]),
                    "observed_at": decoded["observed_at"],
                }
            )
        except (KeyError, TypeError, ValueError, InvalidOperation, ValidationError) as error:
            CACHE_EVENTS.labels(event="error").inc()
            LOGGER.warning("Cache payload is invalid: %s", type(error).__name__)
            return None
        CACHE_EVENTS.labels(event="hit").inc()
        return rate

    async def set(self, key: str, rate: ProviderRate, ttl_seconds: int) -> None:
        payload = json.dumps(
            {
                "sell": str(rate.sell),
                "buy": str(rate.buy),
                "observed_at": rate.observed_utc().isoformat(),
            },
            separators=(",", ":"),
        )
        try:
            await self._redis.set(key, payload, ex=ttl_seconds)
        except RedisError as error:
            CACHE_EVENTS.labels(event="error").inc()
            LOGGER.warning("Cache set failed: %s", type(error).__name__)
            return
        CACHE_EVENTS.labels(event="set").inc()

    async def ping(self) -> bool:
        try:
            return bool(await self._redis.ping())
        except RedisError as error:
            CACHE_EVENTS.labels(event="error").inc()
            LOGGER.warning("Cache ping failed: %s", type(error).__name__)
            return False

    async def close(self) -> None:
        await self._redis.aclose()


def build_cache(settings: Settings) -> RateCache:
    if not settings.cache_enabled:
        return NullRateCache()
    client = Redis.from_url(
        settings.cache_redis_url,
        decode_responses=True,
        socket_connect_timeout=1,
        socket_timeout=1,
        health_check_interval=30,
    )
    return RedisRateCache(client, settings.cache_ttl_seconds)
