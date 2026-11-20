from __future__ import annotations

import asyncio
import shutil

import pytest
from redis.asyncio import Redis
from testcontainers.community.redis import RedisContainer

from exchange.cache import RedisRateCache
from tests.support import RATE

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(shutil.which("docker") is None, reason="Docker is not installed"),
]


async def test_redis_hit_ttl_and_outage() -> None:
    container = RedisContainer("redis:7.4.12-alpine")
    try:
        container.start()
    except Exception as error:  # Docker daemon unavailable
        pytest.skip(f"Docker is unavailable: {type(error).__name__}")

    host = container.get_container_host_ip()
    port = container.get_exposed_port(6379)
    client = Redis.from_url(f"redis://{host}:{port}/0", decode_responses=True)
    cache = RedisRateCache(client, ttl_seconds=1)
    key = "exchange:rate:v1:USD:EUR"
    stopped = False
    try:
        assert await cache.get(key) is None
        await cache.set(key, RATE, 1)
        assert await cache.get(key) == RATE
        await asyncio.sleep(1.2)
        assert await cache.get(key) is None

        container.stop()
        stopped = True
        assert await cache.get(key) is None
        assert await cache.ping() is False
    finally:
        await cache.close()
        if not stopped:
            container.stop()
