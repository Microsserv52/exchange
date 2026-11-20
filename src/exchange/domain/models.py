from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

UTC_DATE_PATTERN = r"^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}$"


class ExchangeRate(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    sell: Annotated[float, Field(gt=0)]
    buy: Annotated[float, Field(gt=0)]
    date: Annotated[str, Field(pattern=UTC_DATE_PATTERN)]
    id_account: Annotated[UUID, Field(alias="id-account")]


class ProviderRate(BaseModel):
    model_config = ConfigDict(frozen=True)

    sell: Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]
    buy: Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]
    observed_at: datetime

    def observed_utc(self) -> datetime:
        if self.observed_at.tzinfo is None:
            return self.observed_at.replace(tzinfo=UTC)
        return self.observed_at.astimezone(UTC)

    def public_date(self) -> str:
        return self.observed_utc().strftime("%Y-%m-%d %H:%M:%S")
