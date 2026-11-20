from __future__ import annotations

from typing import Protocol

from exchange.domain.models import ProviderRate


class ExchangeProvider(Protocol):
    """Boundary between the service and an external exchange-rate provider."""

    name: str

    async def get_rate(self, source: str, target: str) -> ProviderRate: ...

    def is_configured(self) -> bool: ...

    async def close(self) -> None: ...
