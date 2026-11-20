from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from httpx import AsyncClient

from exchange.api.errors import (
    ProviderBusyError,
    ProviderUnavailableError,
    UnsupportedCurrencyError,
)
from tests.support import FakeProvider

CONTRACT = Path(__file__).parent / "contract"


def _schema(name: str) -> dict[str, Any]:
    return json.loads((CONTRACT / "schemas" / name).read_text())


def _example(name: str) -> dict[str, Any]:
    return json.loads((CONTRACT / "examples" / name).read_text())


def test_published_examples_match_schemas() -> None:
    jsonschema.validate(_example("usd-eur.json"), _schema("exchange-rate.schema.json"))
    for error in (
        "error-invalid-currency.json",
        "error-unsupported-currency.json",
        "error-provider-unavailable.json",
    ):
        jsonschema.validate(_example(error), _schema("error.schema.json"))


async def test_success_response_matches_contract(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    response = await client.get("/exchanges/USD/EUR", headers=auth_headers)

    assert response.status_code == 200
    jsonschema.validate(response.json(), _schema("exchange-rate.schema.json"))


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (UnsupportedCurrencyError(), 422),
        (ProviderUnavailableError(), 502),
        (ProviderBusyError(), 503),
    ],
)
async def test_error_response_matches_contract(
    client: AsyncClient,
    auth_headers: dict[str, str],
    provider: FakeProvider,
    error: Exception,
    status: int,
) -> None:
    provider.error = error
    response = await client.get("/exchanges/USD/EUR", headers=auth_headers)

    assert response.status_code == status
    jsonschema.validate(response.json(), _schema("error.schema.json"))


async def test_unauthorized_response_matches_contract(client: AsyncClient) -> None:
    response = await client.get("/exchanges/USD/EUR")

    assert response.status_code == 401
    jsonschema.validate(response.json(), _schema("error.schema.json"))


async def test_invalid_currency_response_matches_contract(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    response = await client.get("/exchanges/ZZZ/EUR", headers=auth_headers)

    assert response.status_code == 422
    jsonschema.validate(response.json(), _schema("error.schema.json"))
