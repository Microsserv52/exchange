from __future__ import annotations

import re

import pycountry

from exchange.api.errors import InvalidCurrencyError

_CODE = re.compile(r"^[A-Z]{3}$")


def normalize_currency(code: str) -> str:
    """Validate an ISO 4217 alphabetic code and return it uppercased."""

    normalized = code.strip().upper()
    if not _CODE.match(normalized) or pycountry.currencies.get(alpha_3=normalized) is None:
        raise InvalidCurrencyError()
    return normalized
