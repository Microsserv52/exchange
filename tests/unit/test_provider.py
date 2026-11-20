from __future__ import annotations

from datetime import UTC
from decimal import Decimal

import httpx
import pytest
import respx

from exchange.api.errors import (
    ProviderBusyError,
    ProviderInvalidResponseError,
    ProviderNotConfiguredError,
    ProviderRateLimitedError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    UnsupportedCurrencyError,
)
from exchange.providers.http import HttpExchangeProvider
from tests.support import make_settings

PROVIDER_URL = "http://provider.test/latest"


def _provider(**overrides):
    return HttpExchangeProvider(make_settings(**overrides))


async def test_numeric_rate_derives_bid_ask_with_spread() -> None:
    provider = _provider(exchange_provider_spread_bps=100)
    try:
        with respx.mock:
            respx.get(PROVIDER_URL).mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "base": "USD",
                        "date": "2026-01-01T00:00:00Z",
                        "rates": {"EUR": 0.82},
                    },
                )
            )
            rate = await provider.get_rate("USD", "EUR")
    finally:
        await provider.close()

    assert rate.sell == Decimal("0.824100")
    assert rate.buy == Decimal("0.815900")
    assert rate.public_date() == "2026-01-01 00:00:00"
    assert rate.observed_at.tzinfo is UTC


async def test_provider_bid_ask_is_used_directly() -> None:
    provider = _provider()
    try:
        with respx.mock:
            respx.get(PROVIDER_URL).mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "base": "USD",
                        "date": "2026-01-01T00:00:00Z",
                        "rates": {"EUR": {"bid": 0.815, "ask": 0.8202}},
                    },
                )
            )
            rate = await provider.get_rate("USD", "EUR")
    finally:
        await provider.close()

    assert rate.sell == Decimal("0.820200")
    assert rate.buy == Decimal("0.815000")


async def test_epoch_timestamp_is_normalized_to_utc() -> None:
    provider = _provider()
    try:
        with respx.mock:
            respx.get(PROVIDER_URL).mock(
                return_value=httpx.Response(
                    200,
                    json={"timestamp": 1767225600, "rates": {"EUR": 0.82}},
                )
            )
            rate = await provider.get_rate("USD", "EUR")
    finally:
        await provider.close()

    assert rate.public_date() == "2026-01-01 00:00:00"


async def test_missing_timestamp_uses_observation_time() -> None:
    provider = _provider()
    try:
        with respx.mock:
            respx.get(PROVIDER_URL).mock(
                return_value=httpx.Response(200, json={"rates": {"EUR": 0.82}})
            )
            rate = await provider.get_rate("USD", "EUR")
    finally:
        await provider.close()

    assert rate.observed_at.tzinfo is UTC


async def test_transient_server_error_is_retried() -> None:
    provider = _provider(exchange_provider_retries=1)
    try:
        with respx.mock:
            respx.get(PROVIDER_URL).mock(
                side_effect=[
                    httpx.Response(503),
                    httpx.Response(200, json={"rates": {"EUR": 0.82}}),
                ]
            )
            rate = await provider.get_rate("USD", "EUR")
    finally:
        await provider.close()

    assert rate.sell > 0


async def test_server_error_after_retries_fails() -> None:
    provider = _provider(exchange_provider_retries=1)
    try:
        with respx.mock:
            respx.get(PROVIDER_URL).mock(return_value=httpx.Response(503))
            with pytest.raises(ProviderUnavailableError):
                await provider.get_rate("USD", "EUR")
    finally:
        await provider.close()


async def test_timeout_maps_to_provider_unavailable() -> None:
    provider = _provider()
    try:
        with respx.mock:
            respx.get(PROVIDER_URL).mock(side_effect=httpx.ConnectTimeout("timeout"))
            with pytest.raises(ProviderTimeoutError):
                await provider.get_rate("USD", "EUR")
    finally:
        await provider.close()


async def test_transport_error_maps_to_provider_unavailable() -> None:
    provider = _provider()
    try:
        with respx.mock:
            respx.get(PROVIDER_URL).mock(side_effect=httpx.ConnectError("refused"))
            with pytest.raises(ProviderUnavailableError):
                await provider.get_rate("USD", "EUR")
    finally:
        await provider.close()


@pytest.mark.parametrize("status", [400, 404, 422])
async def test_unsupported_currency_from_provider(status: int) -> None:
    provider = _provider()
    try:
        with respx.mock:
            respx.get(PROVIDER_URL).mock(return_value=httpx.Response(status))
            with pytest.raises(UnsupportedCurrencyError):
                await provider.get_rate("USD", "EUR")
    finally:
        await provider.close()


@pytest.mark.parametrize("status", [401, 403])
async def test_provider_auth_failure_means_misconfigured(status: int) -> None:
    provider = _provider()
    try:
        with respx.mock:
            respx.get(PROVIDER_URL).mock(return_value=httpx.Response(status))
            with pytest.raises(ProviderNotConfiguredError):
                await provider.get_rate("USD", "EUR")
    finally:
        await provider.close()


async def test_provider_rate_limit_preserves_retry_after() -> None:
    provider = _provider()
    try:
        with respx.mock:
            respx.get(PROVIDER_URL).mock(
                return_value=httpx.Response(429, headers={"Retry-After": "3"})
            )
            with pytest.raises(ProviderRateLimitedError) as caught:
                await provider.get_rate("USD", "EUR")
    finally:
        await provider.close()

    assert caught.value.headers["Retry-After"] == "3"


async def test_malformed_json_is_invalid_response() -> None:
    provider = _provider()
    try:
        with respx.mock:
            respx.get(PROVIDER_URL).mock(return_value=httpx.Response(200, text="not json"))
            with pytest.raises(ProviderInvalidResponseError):
                await provider.get_rate("USD", "EUR")
    finally:
        await provider.close()


async def test_missing_target_rate_is_unsupported_currency() -> None:
    provider = _provider()
    try:
        with respx.mock:
            respx.get(PROVIDER_URL).mock(
                return_value=httpx.Response(200, json={"rates": {"GBP": 0.79}})
            )
            with pytest.raises(UnsupportedCurrencyError):
                await provider.get_rate("USD", "EUR")
    finally:
        await provider.close()


async def test_non_positive_rate_is_invalid_response() -> None:
    provider = _provider()
    try:
        with respx.mock:
            respx.get(PROVIDER_URL).mock(
                return_value=httpx.Response(200, json={"rates": {"EUR": 0}})
            )
            with pytest.raises(ProviderInvalidResponseError):
                await provider.get_rate("USD", "EUR")
    finally:
        await provider.close()


async def test_saturated_concurrency_returns_busy() -> None:
    provider = _provider(exchange_provider_max_concurrency=1)
    await provider._semaphore.acquire()
    try:
        with pytest.raises(ProviderBusyError):
            await provider.get_rate("USD", "EUR")
    finally:
        provider._semaphore.release()
        await provider.close()


async def test_missing_configuration_is_explicit() -> None:
    provider = _provider(exchange_provider_url=None)
    try:
        assert provider.is_configured() is False
        with pytest.raises(ProviderNotConfiguredError):
            await provider.get_rate("USD", "EUR")
    finally:
        await provider.close()


async def test_missing_required_api_key_is_explicit() -> None:
    provider = _provider(exchange_provider_requires_api_key=True)
    try:
        assert provider.is_configured() is False
        with pytest.raises(ProviderNotConfiguredError):
            await provider.get_rate("USD", "EUR")
    finally:
        await provider.close()


@pytest.mark.parametrize("timestamp", [1e100, -1e100, float("inf"), "9" * 400])
async def test_out_of_range_timestamp_is_invalid_response(timestamp) -> None:
    provider = _provider()
    try:
        with respx.mock:
            import json

            # Raw content also exercises non-finite numbers accepted by JSON decoders.
            respx.get(PROVIDER_URL).mock(
                return_value=httpx.Response(
                    200, content=json.dumps({"timestamp": timestamp, "rates": {"EUR": 0.82}})
                )
            )
            with pytest.raises(ProviderInvalidResponseError):
                await provider.get_rate("USD", "EUR")
    finally:
        await provider.close()
