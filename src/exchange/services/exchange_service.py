from __future__ import annotations

import asyncio
from uuid import UUID

from exchange.cache import RateCache
from exchange.config import Settings
from exchange.domain.currencies import normalize_currency
from exchange.domain.models import ExchangeRate, ProviderRate
from exchange.observability import CACHE_EVENTS
from exchange.providers.base import ExchangeProvider


class ExchangeService:
    def __init__(
        self,
        settings: Settings,
        provider: ExchangeProvider,
        cache: RateCache,
    ) -> None:
        self._settings = settings
        self._provider = provider
        self._cache = cache
        self._locks: dict[str, asyncio.Lock] = {}
        self._locks_guard = asyncio.Lock()

    async def get_rate(self, source: str, target: str, account_id: UUID) -> ExchangeRate:
        source_currency = normalize_currency(source)
        target_currency = normalize_currency(target)
        key = self._cache_key(source_currency, target_currency)

        rate = await self._cached_rate(key) if self._settings.cache_enabled else None
        if rate is None:
            if self._settings.cache_enabled:
                rate = await self._provider_rate_with_single_flight(
                    key, source_currency, target_currency
                )
            else:
                rate = await self._provider.get_rate(source_currency, target_currency)

        return ExchangeRate(
            sell=float(rate.sell),
            buy=float(rate.buy),
            date=rate.public_date(),
            id_account=account_id,
        )

    async def _cached_rate(self, key: str) -> ProviderRate | None:
        cached = await self._cache.get(key)
        if cached is not None:
            return cached
        return None

    async def _provider_rate_with_single_flight(
        self, key: str, source: str, target: str
    ) -> ProviderRate:
        lock = await self._lock_for(key)
        if lock.locked():
            CACHE_EVENTS.labels(event="stampede_wait").inc()
        async with lock:
            cached = await self._cached_rate(key)
            if cached is not None:
                return cached
            rate = await self._provider.get_rate(source, target)
            await self._cache.set(key, rate, self._settings.cache_ttl_seconds)
            return rate

    async def _lock_for(self, key: str) -> asyncio.Lock:
        async with self._locks_guard:
            lock = self._locks.get(key)
            if lock is None:
                lock = asyncio.Lock()
                self._locks[key] = lock
            return lock

    def _cache_key(self, source: str, target: str) -> str:
        return f"exchange:rate:{self._settings.exchange_provider_version}:{source}:{target}"
