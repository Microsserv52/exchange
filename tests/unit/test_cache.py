from __future__ import annotations

import fakeredis.aioredis
import pytest
from redis.exceptions import RedisError

from exchange.cache import NullRateCache, RedisRateCache, build_cache
from tests.support import RATE, make_settings


async def test_cache_round_trip_and_ttl() -> None:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    cache = RedisRateCache(redis, ttl_seconds=60)
    try:
        assert await cache.get("exchange:rate:v1:USD:EUR") is None
        await cache.set("exchange:rate:v1:USD:EUR", RATE, 60)
        cached = await cache.get("exchange:rate:v1:USD:EUR")
        assert cached == RATE
        assert 0 < await redis.ttl("exchange:rate:v1:USD:EUR") <= 60
    finally:
        await cache.close()


async def test_expired_entry_is_a_miss() -> None:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    cache = RedisRateCache(redis, ttl_seconds=60)
    key = "exchange:rate:v1:USD:EUR"
    try:
        await cache.set(key, RATE, 60)
        await redis.expire(key, 0)
        assert await cache.get(key) is None
    finally:
        await cache.close()


async def test_corrupt_payload_is_a_safe_miss() -> None:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    cache = RedisRateCache(redis, ttl_seconds=60)
    try:
        await redis.set("exchange:rate:v1:USD:EUR", "not-json")
        assert await cache.get("exchange:rate:v1:USD:EUR") is None
    finally:
        await cache.close()


class BrokenRedis:
    async def get(self, key: str):
        raise RedisError("down")

    async def set(self, key: str, value: str, ex: int):
        raise RedisError("down")

    async def ping(self):
        raise RedisError("down")

    async def aclose(self):
        return None


async def test_redis_errors_degrade_to_miss() -> None:
    cache = RedisRateCache(BrokenRedis(), ttl_seconds=60)  # type: ignore[arg-type]
    assert await cache.get("key") is None
    assert await cache.ping() is False
    await cache.set("key", RATE, 60)
    await cache.close()


async def test_null_cache_is_inert() -> None:
    cache = NullRateCache()
    assert await cache.get("key") is None
    assert await cache.ping() is True
    await cache.set("key", RATE, 60)
    await cache.close()


def test_build_cache_respects_feature_flag() -> None:
    assert isinstance(build_cache(make_settings(cache_enabled=False)), NullRateCache)
    enabled = build_cache(make_settings(cache_enabled=True))
    assert isinstance(enabled, RedisRateCache)


def test_cache_ttl_is_bounded() -> None:
    with pytest.raises(ValueError):
        make_settings(cache_ttl_seconds=0)
    with pytest.raises(ValueError):
        make_settings(cache_ttl_seconds=3601)


@pytest.mark.parametrize("value", ["invalid", "NaN", "Infinity", "-1", "0"])
async def test_invalid_cached_rate_is_a_safe_miss(value: str) -> None:
    import json

    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    cache = RedisRateCache(redis, ttl_seconds=60)
    try:
        await redis.set(
            "key",
            json.dumps({"sell": value, "buy": "0.81", "observed_at": "2026-01-01T00:00:00Z"}),
        )
        assert await cache.get("key") is None
    finally:
        await cache.close()
