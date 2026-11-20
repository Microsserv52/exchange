from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request, Response

from exchange.api.auth import Principal, require_principal
from exchange.domain.models import ExchangeRate
from exchange.services.exchange_service import ExchangeService

router = APIRouter()


def get_exchange_service(request: Request) -> ExchangeService:
    service: ExchangeService = request.app.state.exchange_service
    return service


async def _exchange_rate(
    from_currency: str,
    to_currency: str,
    response: Response,
    principal: Principal,
    service: ExchangeService,
) -> ExchangeRate:
    rate = await service.get_rate(from_currency, to_currency, principal.account_id)
    response.headers["Cache-Control"] = "no-store"
    return rate


@router.get(
    "/exchanges/{from}/{to}",
    response_model=ExchangeRate,
    response_model_exclude_none=True,
    summary="Get the current exchange rate between two currencies.",
    tags=["Exchanges"],
)
async def get_exchange_rate(
    from_currency: Annotated[
        str,
        Path(alias="from", pattern=r"^[A-Za-z]{3}$", min_length=3, max_length=3),
    ],
    to_currency: Annotated[
        str,
        Path(alias="to", pattern=r"^[A-Za-z]{3}$", min_length=3, max_length=3),
    ],
    response: Response,
    principal: Annotated[Principal, Depends(require_principal)],
    service: Annotated[ExchangeService, Depends(get_exchange_service)],
) -> ExchangeRate:
    return await _exchange_rate(from_currency, to_currency, response, principal, service)
