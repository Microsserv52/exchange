from __future__ import annotations

import pytest
from pydantic import ValidationError

from exchange.config import Settings
from tests.support import SECRET, make_settings


def test_provider_url_is_trimmed() -> None:
    settings = make_settings(exchange_provider_url="  https://rates.test/v1/  ")
    assert settings.exchange_provider_url == "https://rates.test/v1"


def test_blank_provider_url_becomes_none() -> None:
    assert make_settings(exchange_provider_url="   ").exchange_provider_url is None


def test_provider_url_must_be_http() -> None:
    with pytest.raises(ValidationError):
        make_settings(exchange_provider_url="rates.test")


def test_log_level_is_normalized_and_validated() -> None:
    assert make_settings(log_level="debug").log_level == "DEBUG"
    with pytest.raises(ValidationError):
        make_settings(log_level="verbose")


def test_short_jwt_secret_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, jwt_secret="short")


def test_secret_is_not_exposed_in_repr() -> None:
    assert SECRET not in repr(make_settings())
