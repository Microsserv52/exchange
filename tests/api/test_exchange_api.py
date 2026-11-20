from __future__ import annotations

import pytest
from httpx import AsyncClient

from exchange.api.errors import (
    ProviderBusyError,
    ProviderInvalidResponseError,
    ProviderNotConfiguredError,
    ProviderRateLimitedError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    UnsupportedCurrencyError,
)
from tests.support import ACCOUNT, FakeProvider, make_token


async def test_returns_stable_exchange_payload(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    response = await client.get("/exchanges/USD/EUR", headers=auth_headers)

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert response.json() == {
        "sell": 0.8202,
        "buy": 0.815,
        "date": "2026-01-01 00:00:00",
        "id-account": str(ACCOUNT),
    }


async def test_lowercase_currencies_are_normalized(
    client: AsyncClient,
    auth_headers: dict[str, str],
    provider: FakeProvider,
) -> None:
    response = await client.get("/exchanges/usd/eur", headers=auth_headers)

    assert response.status_code == 200
    assert provider.calls == [("USD", "EUR")]


@pytest.mark.parametrize(
    "path",
    ["/exchanges/US/EUR", "/exchanges/USD/E", "/exchanges/ZZZ/EUR", "/exchanges/12A/EUR"],
)
async def test_invalid_currency_returns_422(
    client: AsyncClient,
    auth_headers: dict[str, str],
    path: str,
) -> None:
    response = await client.get(path, headers=auth_headers)

    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_CURRENCY"


async def test_missing_authorization_returns_401(client: AsyncClient) -> None:
    response = await client.get("/exchanges/USD/EUR")

    assert response.status_code == 401
    assert response.json() == {"code": "UNAUTHORIZED", "message": "Authentication is required"}


async def test_malformed_authorization_returns_401(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    response = await client.get(
        "/exchanges/USD/EUR",
        headers={"Authorization": auth_headers["Authorization"].replace("Bearer ", "Basic ")},
    )

    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHORIZED"


async def test_expired_token_returns_401(
    client: AsyncClient,
    settings,
) -> None:
    token = make_token(settings, expires_in=-60)
    response = await client.get(
        "/exchanges/USD/EUR",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHORIZED"


async def test_non_uuid_subject_returns_401(
    client: AsyncClient,
    settings,
) -> None:
    token = make_token(settings, subject="not-a-uuid")
    response = await client.get(
        "/exchanges/USD/EUR",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHORIZED"


async def test_wrong_signature_returns_401(
    client: AsyncClient,
    settings,
) -> None:
    token = make_token(settings, secret="another-secret-with-at-least-32-characters")
    response = await client.get(
        "/exchanges/USD/EUR",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401


@pytest.mark.parametrize(
    ("error", "status", "code", "retry_after"),
    [
        (UnsupportedCurrencyError(), 422, "UNSUPPORTED_CURRENCY", None),
        (ProviderUnavailableError(), 502, "PROVIDER_UNAVAILABLE", None),
        (ProviderTimeoutError(), 502, "PROVIDER_UNAVAILABLE", None),
        (ProviderInvalidResponseError(), 502, "PROVIDER_INVALID_RESPONSE", None),
        (ProviderRateLimitedError(5), 429, "RATE_LIMITED", "5"),
        (ProviderBusyError(), 503, "PROVIDER_BUSY", "1"),
        (ProviderNotConfiguredError(), 503, "PROVIDER_NOT_CONFIGURED", None),
    ],
)
async def test_provider_errors_map_to_stable_errors(
    client: AsyncClient,
    auth_headers: dict[str, str],
    provider: FakeProvider,
    error: Exception,
    status: int,
    code: str,
    retry_after: str | None,
) -> None:
    provider.error = error

    response = await client.get("/exchanges/USD/EUR", headers=auth_headers)

    assert response.status_code == status
    assert response.json()["code"] == code
    if retry_after is not None:
        assert response.headers["Retry-After"] == retry_after
    assert "Authorization" not in response.text


async def test_unknown_route_returns_stable_error(client: AsyncClient) -> None:
    response = await client.get("/missing")

    assert response.status_code == 404
    assert response.json() == {"code": "NOT_FOUND", "message": "Resource not found"}


async def test_wrong_method_returns_405(client: AsyncClient) -> None:
    response = await client.post("/exchanges/USD/EUR")

    assert response.status_code == 405
    assert response.json()["code"] == "METHOD_NOT_ALLOWED"
