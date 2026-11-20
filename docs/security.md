---
icon: lucide/shield
---

# Security

Every `GET /exchanges/{from}/{to}` request requires an HS256 bearer JWT.
Exchange validates the token locally using `JWT_SECRET`, requires `exp` and
`sub`, and checks that the subject is a UUID. It permits 30 seconds of clock
skew. `iss` and `aud` are checked when `JWT_ISSUER` and `JWT_AUDIENCE` are
configured. `iat` is validated when present. Roles are not required for rate
lookups. Health, metrics and API documentation endpoints are public; restrict
access to operational endpoints at the deployment boundary as needed.

Use HTTPS at the production ingress and provider boundary. `JWT_SECRET` must
contain at least 32 characters and be shared with the trusted token issuer.
Inject it and `EXCHANGE_PROVIDER_API_KEY` through the deployment's secret
store. Local `.env` files must remain untracked. The local CLI can issue test
tokens and must only be used with development credentials.

Provider keys are sent as bearer credentials by the HTTP adapter. If a key is
required, enable `EXCHANGE_PROVIDER_REQUIRES_API_KEY`; an absent key then
produces `503 PROVIDER_NOT_CONFIGURED`. Provider rate limits return `429`
with `Retry-After`. The per-instance concurrency limit returns `503
PROVIDER_BUSY` with `Retry-After` when saturated.

Errors use the stable `code` and `message` envelope. They do not expose raw
provider payloads, credentials or stack traces. Exchange responses and error
responses include `Cache-Control: no-store`. Account identifiers and tokens
must never become metric labels. See [Observability](observability.md) for
logging and metrics.
