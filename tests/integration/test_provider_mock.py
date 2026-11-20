from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.request
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

from exchange.api.errors import (
    ProviderInvalidResponseError,
    ProviderUnavailableError,
)
from exchange.providers.http import HttpExchangeProvider
from tests.support import make_settings

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[2]


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture
def provider_mock() -> Iterator[tuple[str, subprocess.Popen]]:
    port = _free_port()
    env = {**os.environ, "PORT": str(port), "MOCK_MODE": "ok"}
    process = subprocess.Popen(
        [sys.executable, "mocks/exchange-provider/server.py"],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(50):
            try:
                urllib.request.urlopen(f"{base}/health", timeout=0.5)
                break
            except OSError:
                time.sleep(0.1)
        else:
            raise RuntimeError("provider mock did not start")
        yield base, process
    finally:
        process.terminate()
        process.wait(timeout=5)


def _control(base: str, mode: str) -> None:
    httpx.post(f"{base}/control", params={"mode": mode}, timeout=2).raise_for_status()


async def test_mock_provider_success_and_failure_modes(provider_mock) -> None:
    base, _ = provider_mock
    settings = make_settings(exchange_provider_url=base)
    provider = HttpExchangeProvider(settings)
    try:
        rate = await provider.get_rate("USD", "EUR")
        assert rate.sell > rate.buy > 0
        assert rate.public_date() == "2026-01-01 00:00:00"

        _control(base, "error")
        with pytest.raises(ProviderUnavailableError):
            await provider.get_rate("USD", "EUR")

        _control(base, "malformed")
        with pytest.raises(ProviderInvalidResponseError):
            await provider.get_rate("USD", "EUR")

        _control(base, "ok")
        assert (await provider.get_rate("USD", "EUR")).sell > 0
    finally:
        await provider.close()
