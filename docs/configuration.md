---
icon: lucide/settings
---

# Configuration

Configuration is loaded from environment variables and a local `.env` file.
There are no runtime profiles. `JWT_SECRET` is required by the application;
Compose supplies development values and a local provider URL.

## Environment variables

| Variable | Required | Default | Notes |
| --- | --- | --- | --- |
| `SERVER_PORT` | No | `8080` | HTTP port. |
| `EXCHANGE_PROVIDER_URL` | Yes for readiness | none (Compose: local mock URL) | Provider base URL. |
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
| `JWT_SECRET` | Yes | none (Compose: local-only placeholder) | HS256 secret shared with Auth. |
| `JWT_ISSUER` | No | none | Optional expected `iss`. |
| `JWT_AUDIENCE` | No | none | Optional expected `aud`. |
| `LOG_LEVEL` | No | `INFO` | Structured log level. |

## Secrets

- Never commit `.env`, tokens, passwords or private keys.
- Use a secret manager or Kubernetes `Secret` in deployed environments.
- `JWT_SECRET` must be identical to the value used by Auth and Gateway and must
  be rotated deliberately; rotation invalidates existing tokens.
- Use `EXCHANGE_PROVIDER_API_KEY` for provider credentials; never reuse
  `JWT_SECRET` for outbound authentication.
- Local defaults in `.env.example` are intentionally unsafe for production.

## Local ports

| Variable | Default | Purpose |
| --- | --- | --- |
| `EXCHANGE_PORT` | `8080` | Published Exchange port. |
| `EXCHANGE_REDIS_PORT` | `6381` | Published Redis port. |
| `EXCHANGE_PROVIDER_PORT` | `8082` | Published provider mock port. |
