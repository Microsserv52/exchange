from __future__ import annotations

import logging
from collections.abc import Mapping

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

LOGGER = logging.getLogger(__name__)


class ApiError(Exception):
    """An error that maps to the stable public error envelope."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.headers = dict(headers or {})


class InvalidCurrencyError(ApiError):
    def __init__(self, message: str = "Currency codes must be three ISO 4217 letters") -> None:
        super().__init__(422, "INVALID_CURRENCY", message)


class UnsupportedCurrencyError(ApiError):
    def __init__(self) -> None:
        super().__init__(
            422,
            "UNSUPPORTED_CURRENCY",
            "Currency is not supported by the exchange provider",
        )


class ProviderNotConfiguredError(ApiError):
    def __init__(self) -> None:
        super().__init__(
            503,
            "PROVIDER_NOT_CONFIGURED",
            "Exchange provider is not configured",
        )


class ProviderBusyError(ApiError):
    def __init__(self) -> None:
        super().__init__(
            503,
            "PROVIDER_BUSY",
            "Exchange provider concurrency limit reached",
            headers={"Retry-After": "1"},
        )


class ProviderUnavailableError(ApiError):
    def __init__(self) -> None:
        super().__init__(502, "PROVIDER_UNAVAILABLE", "Exchange provider is unavailable")


class ProviderTimeoutError(ApiError):
    def __init__(self) -> None:
        super().__init__(502, "PROVIDER_UNAVAILABLE", "Exchange provider is unavailable")


class ProviderInvalidResponseError(ApiError):
    def __init__(self) -> None:
        super().__init__(
            502,
            "PROVIDER_INVALID_RESPONSE",
            "Exchange provider returned an invalid response",
        )


class ProviderRateLimitedError(ApiError):
    def __init__(self, retry_after: int = 1) -> None:
        super().__init__(
            429,
            "RATE_LIMITED",
            "Too many exchange requests; retry later",
            headers={"Retry-After": str(max(1, retry_after))},
        )


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def handle_api_error(_: Request, error: ApiError) -> JSONResponse:
        headers = {"Cache-Control": "no-store", **error.headers}
        return JSONResponse(
            status_code=error.status_code,
            content={"code": error.code, "message": error.message},
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, error: RequestValidationError) -> JSONResponse:
        locations = {str(part) for item in error.errors() for part in item.get("loc", ())}
        if {"from", "to"} & locations:
            return JSONResponse(
                status_code=422,
                content={
                    "code": "INVALID_CURRENCY",
                    "message": "Currency codes must be three ISO 4217 letters",
                },
                headers={"Cache-Control": "no-store"},
            )
        return JSONResponse(
            status_code=400,
            content={"code": "VALIDATION_ERROR", "message": "Request validation failed"},
            headers={"Cache-Control": "no-store"},
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(request: Request, error: StarletteHTTPException) -> JSONResponse:
        code = {
            404: "NOT_FOUND",
            405: "METHOD_NOT_ALLOWED",
        }.get(error.status_code, "HTTP_ERROR")
        message = {
            404: "Resource not found",
            405: "Method not allowed",
        }.get(error.status_code, "Request failed")
        return JSONResponse(
            status_code=error.status_code,
            content={"code": code, "message": message},
            headers={"Cache-Control": "no-store"},
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, error: Exception) -> JSONResponse:
        LOGGER.exception(
            "Unhandled request failure",
            extra={"request_id": getattr(request.state, "request_id", None)},
        )
        return JSONResponse(
            status_code=500,
            content={"code": "INTERNAL_ERROR", "message": "Unexpected server error"},
            headers={"Cache-Control": "no-store"},
        )
