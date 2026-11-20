from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from exchange.api.errors import InvalidCurrencyError
from exchange.domain.models import ProviderRate
from exchange.services.exchange_service import ExchangeService
from tests.support import ACCOUNT, FakeProvider, MemoryCache, make_settings

RATE = ProviderRate(
    sell=Decimal("0.820200"),
    buy=Decimal("0.815000"),
    observed_at=datetime(2026, 1, 1, tzinfo=UTC),
)


async def test_cache_miss_then_hit_uses_provider_once() -> None:
    provider = FakeProvider(rate=RATE)
    cache = MemoryCache()
    service = ExchangeService(make_settings(cache_enabled=True), provider, cache)

    first = await service.get_rate("usd", "eur", ACCOUNT)
    second = await service.get_rate("USD", "EUR", ACCOUNT)

    assert first == second
    assert provider.calls == [("USD", "EUR")]
    assert cache.sets == 1
    assert cache.gets == 3


async def test_cache_disabled_calls_provider_every_time() -> None:
    provider = FakeProvider(rate=RATE)
    cache = MemoryCache()
    service = ExchangeService(make_settings(cache_enabled=False), provider, cache)

    await service.get_rate("USD", "EUR", ACCOUNT)
    await service.get_rate("USD", "EUR", ACCOUNT)

    assert provider.calls == [("USD", "EUR"), ("USD", "EUR")]
    assert cache.gets == 0
    assert cache.sets == 0


async def test_concurrent_misses_are_single_flight() -> None:
    class SlowProvider(FakeProvider):
        def __init__(self) -> None:
            super().__init__(rate=RATE)
            self.started = asyncio.Event()
            self.release = asyncio.Event()

        async def get_rate(self, source: str, target: str) -> ProviderRate:
            self.calls.append((source, target))
            self.started.set()
            await self.release.wait()
            return self.rate

    provider = SlowProvider()
    cache = MemoryCache()
    service = ExchangeService(make_settings(cache_enabled=True), provider, cache)

    tasks = [asyncio.create_task(service.get_rate("USD", "EUR", ACCOUNT)) for _ in range(8)]
    await provider.started.wait()
    await asyncio.sleep(0.01)
    provider.release.set()
    results = await asyncio.gather(*tasks)

    assert len(results) == 8
    assert provider.calls == [("USD", "EUR")]
    assert cache.sets == 1


async def test_invalid_currency_is_rejected_before_provider_call() -> None:
    provider = FakeProvider(rate=RATE)
    service = ExchangeService(make_settings(), provider, MemoryCache())

    with pytest.raises(InvalidCurrencyError):
        await service.get_rate("ZZZ", "EUR", ACCOUNT)

    assert provider.calls == []


def test_cache_key_contains_provider_version() -> None:
    settings = make_settings(cache_enabled=True, exchange_provider_version="v9")
    service = ExchangeService(settings, FakeProvider(rate=RATE), MemoryCache())

    assert service._cache_key("USD", "EUR") == "exchange:rate:v9:USD:EUR"
