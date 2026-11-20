from __future__ import annotations

import logging
import re
import time
import uuid
from contextvars import ContextVar

from fastapi import FastAPI, Request
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pythonjsonlogger import json as jsonlogger
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

REQUEST_ID_HEADER = "X-Request-Id"
REQUEST_ID = ContextVar("request_id", default="-")
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

PROVIDER_REQUESTS = Counter(
    "exchange_provider_requests_total",
    "Provider HTTP requests by outcome.",
    ["provider", "outcome"],
)
PROVIDER_LATENCY = Histogram(
    "exchange_provider_request_duration_seconds",
    "Provider HTTP request latency.",
    ["provider"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5),
)
PROVIDER_ERRORS = Counter(
    "exchange_provider_errors_total",
    "Provider failures by stable error code.",
    ["provider", "code"],
)
CACHE_EVENTS = Counter(
    "exchange_cache_events_total",
    "Cache events. Stale rates are never served, so no stale event exists.",
    ["event"],
)
HTTP_REQUESTS = Counter(
    "exchange_http_requests_total",
    "HTTP requests by route.",
    ["method", "path", "status"],
)
HTTP_LATENCY = Histogram(
    "exchange_http_request_duration_seconds",
    "HTTP request latency by route.",
    ["method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5),
)


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = REQUEST_ID.get()
        return True


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        candidate = request.headers.get(REQUEST_ID_HEADER, "")
        request_id = candidate if _VALID_REQUEST_ID.match(candidate) else str(uuid.uuid4())
        token = REQUEST_ID.set(request_id)
        request.state.request_id = request_id
        started = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            REQUEST_ID.reset(token)
        response.headers[REQUEST_ID_HEADER] = request_id
        logging.getLogger("exchange.access").info(
            "request completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            },
        )
        return response


class MetricsMiddleware(BaseHTTPMiddleware):
    _SKIP_PREFIXES = ("/health", "/actuator/health", "/info", "/metrics")

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path.startswith(self._SKIP_PREFIXES):
            return await call_next(request)
        started = time.perf_counter()
        response = await call_next(request)
        route = request.scope.get("route")
        path = getattr(route, "path", None) or "unmatched"
        HTTP_REQUESTS.labels(
            method=request.method,
            path=path,
            status=str(response.status_code),
        ).inc()
        HTTP_LATENCY.labels(method=request.method, path=path).observe(time.perf_counter() - started)
        return response


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(
        jsonlogger.JsonFormatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s %(request_id)s",
            rename_fields={
                "asctime": "timestamp",
                "levelname": "level",
                "name": "logger",
            },
        )
    )
    handler.addFilter(RequestIdFilter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    for noisy in ("httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def install_metrics(app: FastAPI) -> None:
    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
