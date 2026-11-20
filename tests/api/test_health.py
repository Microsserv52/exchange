from __future__ import annotations

from httpx import AsyncClient

from exchange.main import create_app
from tests.support import FakeProvider, MemoryCache, client_for, make_settings


async def test_health_and_info_endpoints(client: AsyncClient) -> None:
    health = await client.get("/health")
    live = await client.get("/health/live")
    ready = await client.get("/health/ready")
    info = await client.get("/info")

    assert health.status_code == 200
    assert health.json()["status"] == "UP"
    assert health.json()["components"] == {
        "provider": {"status": "UP"},
        "cache": {"status": "DISABLED"},
    }
    assert live.json() == {"status": "UP"}
    assert ready.status_code == 200
    assert info.json()["service"] == "exchange"
    assert info.json()["providerConfigured"] is True
    assert "secret" not in info.text.lower()


async def test_platform_compatible_health_aliases(client: AsyncClient) -> None:
    assert (await client.get("/actuator/health")).status_code == 200
    assert (await client.get("/actuator/health/liveness")).json() == {"status": "UP"}
    assert (await client.get("/actuator/health/readiness")).status_code == 200


async def test_readiness_fails_when_provider_is_not_configured() -> None:
    application = create_app(
        make_settings(exchange_provider_url=None),
        provider=FakeProvider(configured=False),
        cache=MemoryCache(),
    )
    async with client_for(application) as client:
        health = await client.get("/health")
        ready = await client.get("/health/ready")
        live = await client.get("/health/live")
        info = await client.get("/info")

    assert health.status_code == 503
    assert health.json()["status"] == "DOWN"
    assert ready.status_code == 503
    assert live.status_code == 200
    assert info.json()["providerConfigured"] is False


async def test_readiness_degrades_but_stays_ready_when_redis_is_down() -> None:
    cache = MemoryCache()
    cache.ping_result = False
    application = create_app(
        make_settings(cache_enabled=True),
        provider=FakeProvider(),
        cache=cache,
    )
    async with client_for(application) as client:
        health = await client.get("/health")
        ready = await client.get("/health/ready")

    assert health.status_code == 200
    assert health.json()["status"] == "DEGRADED"
    assert health.json()["components"]["cache"] == {"status": "DOWN"}
    assert ready.status_code == 200


async def test_prometheus_endpoint_is_exposed(client: AsyncClient, auth_headers) -> None:
    await client.get("/exchanges/USD/EUR", headers=auth_headers)
    response = await client.get("/metrics")

    assert response.status_code == 200
    assert "exchange_provider_requests_total" in response.text
