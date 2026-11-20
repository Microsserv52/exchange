from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Header, Request

from exchange.api.errors import ApiError
from exchange.config import Settings


@dataclass(frozen=True)
class Principal:
    account_id: UUID


class JwtAuthenticator:
    def __init__(self, settings: Settings) -> None:
        self._secret = settings.jwt_secret.get_secret_value()
        self._issuer = settings.jwt_issuer
        self._audience = settings.jwt_audience

    def authenticate(self, authorization: str | None) -> Principal:
        if not authorization or not authorization.startswith("Bearer "):
            raise ApiError(401, "UNAUTHORIZED", "Authentication is required")
        token = authorization.removeprefix("Bearer ").strip()
        if not token:
            raise ApiError(401, "UNAUTHORIZED", "Authentication is required")
        try:
            payload = jwt.decode(
                token,
                self._secret,
                algorithms=["HS256"],
                audience=self._audience,
                issuer=self._issuer,
                leeway=30,
                options={
                    "require": ["exp", "sub"],
                    "verify_aud": self._audience is not None,
                    "verify_iss": self._issuer is not None,
                },
            )
        except jwt.InvalidTokenError as error:
            raise ApiError(401, "UNAUTHORIZED", "Authentication is required") from error

        try:
            account_id = UUID(str(payload["sub"]))
        except (KeyError, TypeError, ValueError) as error:
            raise ApiError(401, "UNAUTHORIZED", "Authentication is required") from error
        return Principal(account_id=account_id)


async def require_principal(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> Principal:
    authenticator: JwtAuthenticator = request.app.state.authenticator
    return authenticator.authenticate(authorization)
