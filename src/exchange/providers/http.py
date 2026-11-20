from __future__ import annotations

import asyncio
import logging
import time
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from exchange.api.errors import (
    ProviderBusyError,
    ProviderInvalidResponseError,
    ProviderNotConfiguredError,
    ProviderRateLimitedError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    UnsupportedCurrencyError,
)
from exchange.config import Settings
from exchange.domain.models import ProviderRate
from exchange.observability import PROVIDER_ERRORS, PROVIDER_LATENCY, PROVIDER_REQUESTS

LOGGER = logging.getLogger(__name__)
_RETRYABLE_STATUS = {408, 425, 500, 502, 503, 504}
_UNSUPPORTED_STATUS = {400, 404, 422}
_QUANTUM = Decimal("0.000001")


class HttpExchangeProvider:
    """Adapter for a generic ``GET /latest`` JSON rate provider."""

    name = "http"

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._base_url = settings.exchange_provider_url
        self._api_key = (
            settings.exchange_provider_api_key.get_secret_value()
            if settings.exchange_provider_api_key is not None
            else None
        )
        self._semaphore = asyncio.Semaphore(settings.exchange_provider_max_concurrency)
        headers = {"Accept": "application/json", "User-Agent": "microsserv52-exchange/0.1.0"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        timeout = httpx.Timeout(
            settings.exchange_provider_timeout_seconds,
            connect=min(1.0, settings.exchange_provider_timeout_seconds),
        )
        self._client = client or httpx.AsyncClient(
            base_url=self._base_url or "",
            headers=headers,
            timeout=timeout,
            follow_redirects=False,
        )
        self._owns_client = client is None

    def is_configured(self) -> bool:
        if not self._base_url:
            return False
        return not self._settings.exchange_provider_requires_api_key or bool(self._api_key)

    async def get_rate(self, source: str, target: str) -> ProviderRate:
        if not self.is_configured():
            raise ProviderNotConfiguredError()
        if self._semaphore.locked():
            raise ProviderBusyError()

        async with self._semaphore:
            return await self._request_with_retries(source, target)

    async def _request_with_retries(self, source: str, target: str) -> ProviderRate:
        attempts = self._settings.exchange_provider_retries + 1
        last_error: Exception | None = None
        for attempt in range(attempts):
            started = time.perf_counter()
            try:
                response = await self._client.get(
                    "/latest",
                    params={"base": source, "symbols": target},
                )
            except httpx.TimeoutException as error:
                self._observe("timeout", started)
                last_error = error
                if attempt + 1 < attempts:
                    await self._backoff(attempt)
                    continue
                self._record_error("PROVIDER_UNAVAILABLE")
                raise ProviderTimeoutError() from error
            except httpx.TransportError as error:
                self._observe("transport_error", started)
                last_error = error
                if attempt + 1 < attempts:
                    await self._backoff(attempt)
                    continue
                self._record_error("PROVIDER_UNAVAILABLE")
                raise ProviderUnavailableError() from error
            except httpx.HTTPError as error:
                self._observe("transport_error", started)
                self._record_error("PROVIDER_UNAVAILABLE")
                raise ProviderUnavailableError() from error

            self._observe(_outcome_for_status(response.status_code), started)
            status = response.status_code

            if status in _UNSUPPORTED_STATUS:
                self._record_error("UNSUPPORTED_CURRENCY")
                raise UnsupportedCurrencyError()
            if status in {401, 403}:
                self._record_error("PROVIDER_NOT_CONFIGURED")
                raise ProviderNotConfiguredError()
            if status == 429:
                self._record_error("RATE_LIMITED")
                raise ProviderRateLimitedError(_retry_after(response))
            if status in _RETRYABLE_STATUS:
                last_error = ProviderUnavailableError()
                if attempt + 1 < attempts:
                    await self._backoff(attempt)
                    continue
                self._record_error("PROVIDER_UNAVAILABLE")
                raise ProviderUnavailableError()
            if status >= 500:
                self._record_error("PROVIDER_UNAVAILABLE")
                raise ProviderUnavailableError()
            if status >= 400:
                self._record_error("PROVIDER_INVALID_RESPONSE")
                raise ProviderInvalidResponseError()
            if status != 200:
                self._record_error("PROVIDER_INVALID_RESPONSE")
                raise ProviderInvalidResponseError()

            try:
                payload = response.json()
            except ValueError as error:
                self._record_error("PROVIDER_INVALID_RESPONSE")
                raise ProviderInvalidResponseError() from error

            try:
                return self._extract_rate(payload, target)
            except UnsupportedCurrencyError, ProviderInvalidResponseError:
                raise
            except (
                InvalidOperation,
                TypeError,
                ValueError,
                KeyError,
                OverflowError,
                OSError,
            ) as error:
                self._record_error("PROVIDER_INVALID_RESPONSE")
                raise ProviderInvalidResponseError() from error

        self._record_error("PROVIDER_UNAVAILABLE")
        raise ProviderUnavailableError() from last_error

    def _extract_rate(self, payload: Any, target: str) -> ProviderRate:
        if not isinstance(payload, dict):
            raise ProviderInvalidResponseError()
        rates = payload.get("rates", payload.get("conversion_rates"))
        if not isinstance(rates, dict):
            raise ProviderInvalidResponseError()

        raw = rates.get(target, rates.get(target.upper()))
        if raw is None:
            raise UnsupportedCurrencyError()

        observed_at = self._extract_timestamp(payload)
        if isinstance(raw, dict):
            sell = _decimal(raw.get("ask", raw.get("sell")))
            buy = _decimal(raw.get("bid", raw.get("buy")))
            mid = _decimal(raw.get("rate", raw.get("mid", raw.get("value"))))
        else:
            sell = None
            buy = None
            mid = _decimal(raw)

        if sell is None and mid is not None:
            sell = mid * (Decimal(1) + self._half_spread())
        if buy is None and mid is not None:
            buy = mid * (Decimal(1) - self._half_spread())
        if sell is None or buy is None:
            raise ProviderInvalidResponseError()

        sell = sell.quantize(_QUANTUM)
        buy = buy.quantize(_QUANTUM)
        if sell <= 0 or buy <= 0:
            raise ProviderInvalidResponseError()
        return ProviderRate(sell=sell, buy=buy, observed_at=observed_at)

    def _extract_timestamp(self, payload: dict[str, Any]) -> datetime:
        for field in ("timestamp", "time_last_update_unix", "date", "observed_at", "time"):
            value = payload.get(field)
            if value is None or value == "":
                continue
            parsed = _parse_timestamp(value)
            if parsed is None:
                raise ProviderInvalidResponseError()
            return parsed
        return datetime.now(UTC)

    def _half_spread(self) -> Decimal:
        return Decimal(str(self._settings.exchange_provider_spread_bps)) / Decimal(20000)

    def _observe(self, outcome: str, started: float) -> None:
        PROVIDER_REQUESTS.labels(provider=self.name, outcome=outcome).inc()
        PROVIDER_LATENCY.labels(provider=self.name).observe(time.perf_counter() - started)

    def _record_error(self, code: str) -> None:
        PROVIDER_ERRORS.labels(provider=self.name, code=code).inc()

    async def _backoff(self, attempt: int) -> None:
        await asyncio.sleep(min(0.05 * (2**attempt), 0.25))

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()


def _decimal(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation, ValueError:
        return None


def _parse_timestamp(value: Any) -> datetime | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return datetime.fromtimestamp(float(value), tz=UTC)
    if isinstance(value, str):
        text = value.strip()
        if text.isdigit():
            return datetime.fromtimestamp(float(text), tz=UTC)
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    return None


def _outcome_for_status(status: int) -> str:
    if status == 200:
        return "ok"
    if status == 429:
        return "rate_limited"
    if status in {401, 403}:
        return "auth"
    if status in _UNSUPPORTED_STATUS:
        return "unsupported"
    if status >= 500:
        return "server_error"
    return "client_error"


def _retry_after(response: httpx.Response) -> int:
    try:
        return max(1, int(response.headers.get("Retry-After", "1")))
    except ValueError:
        return 1
