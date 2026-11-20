# Exchange

Currency conversion microservice for the [Microsserv52 platform](https://github.com/Microsserv52/platform).
Exchange validates ISO 4217 currencies, calls a configurable third-party
provider through an adapter, optionally caches rates in Redis and returns the
stable platform response. It is implemented with Python 3.14, `uv` and FastAPI.

[![Exchange CI](https://github.com/Microsserv52/exchange/actions/workflows/ci.yml/badge.svg)](https://github.com/Microsserv52/exchange/actions/workflows/ci.yml)
[![Documentation](https://github.com/Microsserv52/exchange/actions/workflows/docs.yml/badge.svg)](https://microsserv52.github.io/exchange/)

> [!IMPORTANT]
> The canonical HTTP contract lives in
> [`Microsserv52/exchange-interface`](https://github.com/Microsserv52/exchange-interface).
> Provider payloads are never part of the platform contract.

## Quick start

The supported clean-machine path is fully containerized. It requires Git,
Docker and Docker Compose v2; it does not require host Python, `uv` or Redis.

```bash
git clone --recurse-submodules https://github.com/Microsserv52/exchange.git
cd exchange
./scripts/bootstrap.sh
curl http://localhost:8080/health
```

`bootstrap.sh` creates `.env` from `.env.example`, builds the image with the
repository `Dockerfile`, starts Exchange, Redis and the deterministic provider
mock, waits for readiness, then runs an authenticated smoke check.

| URL | Purpose |
| --- | --- |
| `http://localhost:8080` | Exchange API |
| `http://localhost:8080/health` | Overall health |
| `http://localhost:8080/health/live` | Liveness |
| `http://localhost:8080/health/ready` | Readiness |
| `http://localhost:8080/actuator/health/readiness` | Platform-compatible readiness alias |
| `http://localhost:8080/metrics` | Prometheus scrape endpoint |
| `http://localhost:8080/docs` | OpenAPI UI |
| `http://localhost:8082` | Deterministic provider mock |

Stop with `./scripts/stop.sh`; remove only this repository's named volumes with
`./scripts/reset.sh --yes`.

## Endpoint

`GET /exchanges/{from}/{to}` requires an HS256 bearer JWT whose `sub` is the
account UUID.

```bash
TOKEN="$(docker compose exec -T exchange .venv/bin/python -m exchange.cli token \
  --sub 0195ae95-5be7-7dd3-b35d-7a7d87c404fb)"

curl -s http://localhost:8080/exchanges/USD/EUR \
  -H "Authorization: Bearer ${TOKEN}"
```

```json
{
  "sell": 0.8202,
  "buy": 0.815,
  "date": "2026-01-01 00:00:00",
  "id-account": "0195ae95-5be7-7dd3-b35d-7a7d87c404fb"
}
```

`date` is UTC in `YYYY-MM-DD HH:MM:SS` form. Unsupported or invalid currencies
return `422`. Provider timeouts, failures and malformed payloads return `502`.
Provider rate limiting returns `429`; missing configuration or instance
saturation returns `503`.

See [API and errors](docs/api.md) for the full reference.

## Environment variables

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `SERVER_PORT` | No | `8080` | HTTP listen port. |
| `EXCHANGE_PROVIDER_URL` | Yes in production | local mock URL | Provider base URL. |
| `EXCHANGE_PROVIDER_API_KEY` | Provider-dependent | none | Provider credential; never commit it. |
| `EXCHANGE_PROVIDER_REQUIRES_API_KEY` | No | `false` | Return `503` when a required key is missing. |
| `EXCHANGE_PROVIDER_VERSION` | No | `v1` | Cache-key namespace for provider changes. |
| `EXCHANGE_PROVIDER_TIMEOUT_SECONDS` | No | `2` | Connect/read timeout. |
| `EXCHANGE_PROVIDER_RETRIES` | No | `1` | Extra attempts for safe transient failures, maximum 3. |
| `EXCHANGE_PROVIDER_MAX_CONCURRENCY` | No | `20` | Per-instance provider concurrency limit. |
| `EXCHANGE_PROVIDER_SPREAD_BPS` | No | `0` | Total spread in basis points; half is applied on either side of a mid rate. |
| `CACHE_REDIS_URL` | No | `redis://redis:6379/0` | Redis-compatible cache endpoint. |
| `CACHE_ENABLED` | No | `false` | Explicit cache feature flag. |
| `CACHE_TTL_SECONDS` | No | `60` | Rate cache TTL, 1-3600 seconds. |
| `JWT_SECRET` | Yes | local-only placeholder | HS256 secret shared with Auth. |
| `JWT_ISSUER` | No | none | Optional expected `iss`. |
| `JWT_AUDIENCE` | No | none | Optional expected `aud`. |
| `LOG_LEVEL` | No | `INFO` | Structured log level. |

See [Configuration](docs/configuration.md) for the complete reference and
secret guidance.

## Provider adapter

`exchange.providers.http.HttpExchangeProvider` expects:

```http
GET {EXCHANGE_PROVIDER_URL}/latest?base=USD&symbols=EUR
Authorization: Bearer <EXCHANGE_PROVIDER_API_KEY>
Accept: application/json
```

The response must contain a `rates` object. Each entry may be a number (mid
rate) or an object with `bid`/`ask` or `buy`/`sell`. Optional timestamps are
read from `timestamp`, `time_last_update_unix`, `date`, `observed_at` or `time`.
The adapter normalizes the payload and never exposes provider fields directly.

Only timeouts, transport errors and `408`/`425`/`5xx` responses are retried.
`4xx` responses are not retried. `400`, `404` and `422` mean the currency is
unsupported by the provider. `401`/`403` mean the provider is misconfigured.
`429` returns `RATE_LIMITED` with `Retry-After`.

A replacement provider implements `exchange.providers.base.ExchangeProvider`.
Tests inject a deterministic fake adapter; the local Compose stack runs
`mocks/exchange-provider`, which is never deployed to production.

## Cache and resilience

- Key: `exchange:rate:{EXCHANGE_PROVIDER_VERSION}:{FROM}:{TO}`.
- TTL: `CACHE_TTL_SECONDS`, default 60 seconds.
- Per-key `asyncio.Lock` prevents concurrent cache misses from stampeding the
  provider in a single process.
- Redis errors are cache misses; the request continues to the provider.
- Stale rates are never served. The contract has no stale-data allowance.
- Provider concurrency is bounded by a semaphore; saturation returns
  `503 PROVIDER_BUSY` with `Retry-After`.
- Caching is disabled by default until integration tests prove TTL and outage
  behavior in the target environment.

See [Cache and resilience](docs/cache.md).

## Local development

```bash
uv sync --frozen
uv run ruff format --check src tests
uv run ruff check src tests
uv run mypy src
uv run pytest
uv run pytest --cov --cov-report=term-missing
```

The standalone container path remains authoritative. Redis integration tests
use Testcontainers when Docker is available.

## Validation modes

**Standalone** uses only this repository:

```bash
./scripts/bootstrap.sh
./scripts/smoke.sh
./scripts/stop.sh
```

**Full platform** uses the platform Compose or Kubernetes topology. Publish the
image as `ghcr.io/microsserv52/exchange:sha-<full-commit-sha>`, point
`EXCHANGE_IMAGE` and `EXCHANGE_URL` at that immutable image and service, keep the
local provider mock for development, and run the platform integration smoke
tests. The platform repository owns the integration manifests; this repository
tests the provider adapter, cache and HTTP behavior from the service side.

## Image publication

CI publishes only after format, lint, type-check, tests, coverage, CodeQL,
Compose and container checks pass:

```text
ghcr.io/microsserv52/exchange:sha-<full-commit-sha>
```

Release tags may also publish `ghcr.io/microsserv52/exchange:v<version>`.
Kubernetes and production deployments must use an immutable digest or `sha-`
tag, never `latest`.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Readiness returns `503` | Set `EXCHANGE_PROVIDER_URL`; set an API key if the provider requires one. |
| `401 UNAUTHORIZED` | Create a fresh token; confirm `JWT_SECRET` matches the token signer. |
| `422 INVALID_CURRENCY` | Use three ISO 4217 letters, for example `USD`. |
| `422 UNSUPPORTED_CURRENCY` | The provider rejected the currency pair. |
| `502 PROVIDER_UNAVAILABLE` | Inspect the mock/provider logs and timeout settings. |
| `429 RATE_LIMITED` | The provider asked the service to retry later. |
| Cache tests fail | Set `CACHE_ENABLED=true`; confirm Redis is healthy. |
| Port already in use | Change `EXCHANGE_PORT`, `EXCHANGE_REDIS_PORT` or `EXCHANGE_PROVIDER_PORT`. |

## Documentation

- [Architecture](docs/architecture.md)
- [Configuration](docs/configuration.md)
- [API and errors](docs/api.md)
- [Provider adapter](docs/provider.md)
- [Cache and resilience](docs/cache.md)
- [Observability](docs/observability.md)
- [Security](docs/security.md)
- [Kubernetes and rollback](docs/kubernetes.md)
- [Development and validation](docs/development.md)
- [Changelog and versioning](docs/changelog.md)

## Links

- [Microsserv52 organization](https://github.com/Microsserv52)
- [Platform repository](https://github.com/Microsserv52/platform)
- [Published platform documentation](https://microsserv52.github.io/platform/)
- [Exchange service repository](https://github.com/Microsserv52/exchange)
- [Exchange interface repository](https://github.com/Microsserv52/exchange-interface)
- [Exchange interface documentation](https://microsserv52.github.io/exchange-interface/)
