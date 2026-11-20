---
icon: lucide/hammer
---

# Development and validation

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

## Tests

| Layer | Location | Notes |
| --- | --- | --- |
| Unit | `tests/unit/` | Cache, provider, service logic with fakes. |
| API | `tests/api/` | Endpoints, auth, errors, health, `/metrics`. |
| Contract | `tests/contract/` | Response shapes against interface snapshots. |
| Integration | `tests/integration/` | Provider mock and Redis Testcontainers. |

Integration tests are marked `integration` and require Docker or a local
external dependency.

## Local commands

```bash
uv run python -m exchange.cli token --sub 0195ae95-5be7-7dd3-b35d-7a7d87c404fb
uv run python -m exchange.cli token --sub ... --roles ROLE_ADMIN,ROLE_USER
uv run uvicorn exchange.main:app
```

## Local provider mock

```bash
docker compose up --detach
docker compose exec provider /bin/sh -c 'echo ok'
curl 'http://localhost:8082/latest?base=USD&symbols=EUR'
curl -X POST http://localhost:8082/control?mode=error
```

Modes: `ok`, `error`, `timeout`, `malformed`, `rate_limit`, `unsupported`.
Rates are fixed relative to USD and include deterministic bid/ask values.
`MOCK_API_KEY` optionally requires an `Authorization: Bearer` header; never set
it to a real credential.

The mock refuses to start when `ENV` or `APP_ENV` is `prod` or `production`
(case-insensitive); it exits with status `1` before binding the port. Compose
never sets those variables, and no Kubernetes manifest or CI workflow deploys
the mock.

## Validation

- **Standalone**: run the local Compose stack and execute
  `./scripts/bootstrap.sh`, `./scripts/smoke.sh`, `./scripts/stop.sh`.
- **Full platform**: publish the image as
  `ghcr.io/microsserv52/exchange:sha-<full-commit-sha>`, point `EXCHANGE_IMAGE`
  and `EXCHANGE_URL` at that immutable image and service, keep the local
  provider mock for development, and run the platform integration smoke tests.

## Coverage

Coverage is required to be at or above `85%` per bundle. Integration tests run
with coverage enabled.

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