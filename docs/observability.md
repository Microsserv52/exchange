---
icon: lucide/activity
---

# Observability

## Health endpoints

| Endpoint | Purpose | Failure behavior |
| --- | --- | --- |
| `GET /health/live` | Process liveness. | Returns `200` while the endpoint is serving. |
| `GET /health/ready` | Readiness, including provider and optional cache. | `503` when the provider is unconfigured. |
| `GET /health` | Overall health. | Same as readiness. |
| `GET /actuator/health/readiness` | Platform-compatible readiness alias. | Same as readiness. |
| `GET /metrics` | Prometheus scrape endpoint. | `200`. |

Redis is excluded from readiness unless `CACHE_ENABLED=true`. A Redis outage
keeps the service ready and increases provider load.

## Metrics

Prometheus metrics:

| Metric | Meaning |
| --- | --- |
| `exchange_http_requests_total` | HTTP request count by method, path and status. |
| `exchange_http_request_duration_seconds` | HTTP latency by method and route. |
| `exchange_provider_requests_total` | Provider calls by outcome. |
| `exchange_provider_request_duration_seconds` | Provider latency. |
| `exchange_provider_errors_total` | Provider failures by stable error code. |
| `exchange_cache_events_total` | Cache events. |

Labels are intentionally low cardinality. Do not add account IDs, currencies or
request IDs as metric labels.

## Logs

The service logs structured JSON with:

- timestamp in UTC;
- level and logger;
- `request_id` from `X-Request-Id` when supplied, otherwise a generated UUID;
- `method`, `path` and `status` on completed requests.

Secrets, JWTs and provider credentials are never logged.

## Suggested alerts

| Alert | Condition |
| --- | --- |
| Provider saturation | `exchange_provider_errors_total` increasing while `up` is low. |
| Elevated 5xx | `exchange_http_requests_total{status=~"5.."}` rate above baseline. |
| Cache degradation | `exchange_cache_events_total{event="error"}` increasing. |
| Latency regression | p95 `exchange_http_request_duration_seconds` above the agreed exchange SLO. |
