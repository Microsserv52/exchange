from __future__ import annotations

import jwt
import pytest

from exchange import cli
from exchange.config import get_settings

SECRET = "test-secret-with-at-least-32-characters-long"


@pytest.fixture(autouse=True)
def _settings(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)
    monkeypatch.setenv("JWT_ISSUER", "https://identity.test")
    monkeypatch.setenv("JWT_AUDIENCE", "exchange")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_token_command_emits_verifiable_token(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["token", "--sub", "account-1", "--roles", "ROLE_USER,ROLE_ADMIN"]) == 0

    token = capsys.readouterr().out.strip()
    payload = jwt.decode(
        token,
        SECRET,
        algorithms=["HS256"],
        audience="exchange",
        issuer="https://identity.test",
    )
    assert payload["sub"] == "account-1"
    assert payload["roles"] == ["ROLE_USER", "ROLE_ADMIN"]
    assert payload["exp"] - payload["iat"] == 3600


def test_token_command_clamps_ttl(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["token", "--ttl", "999999"]) == 0

    token = capsys.readouterr().out.strip()
    payload = jwt.decode(token, SECRET, algorithms=["HS256"], audience="exchange")
    assert payload["exp"] - payload["iat"] == 86400


def test_unknown_command_is_rejected() -> None:
    with pytest.raises(SystemExit):
        cli.main(["unknown"])
