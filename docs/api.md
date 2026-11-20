---
icon: lucide/route
---

# API and errors

The canonical OpenAPI document is
[`openapi/exchange.yaml`](https://github.com/Microsserv52/exchange-interface/blob/main/openapi/exchange.yaml).
This page summarizes the behavior implemented by the service.

## Authentication

- Every exchange request requires a valid HS256 bearer JWT.
- The token `sub` must be the account UUID.
- Tokens are validated locally; Exchange never calls Auth per request.
- Missing, expired or malformed tokens return `401 UNAUTHORIZED`.

## Endpoint

| Method | Path | Authentication | Success | Errors |
| --- | --- | --- | --- | --- |
| `GET` | `/exchanges/{from}/{to}` | Bearer JWT | `200` exchange rate | `401`, `422`, `429`, `502`, `503` |

### Request

```http
GET /exchanges/USD/EUR HTTP/1.1
Authorization: Bearer <token>
X-Request-Id: optional-id
```

Currency codes are exactly three ASCII letters. The service accepts
`[A-Za-z]{3}` and normalizes them to upper case before calling the provider.

### Response

```json
{
  "sell": 0.8202,
  "buy": 0.815,
  "date": "2026-01-01 00:00:00",
  "id-account": "0195ae95-5be7-7dd3-b35d-7a7d87c404fb"
}
```

- `sell` is the provider's ask price converted to the target currency.
- `buy` is the provider's bid price converted to the target currency.
- `date` is UTC in `YYYY-MM-DD HH:MM:SS` form.
- `id-account` echoes the authenticated account UUID.

Responses always carry `Cache-Control: no-store`.

## Error envelope

```json
{
  "code": "PROVIDER_UNAVAILABLE",
  "message": "Exchange provider is unavailable"
}
```

`message` never contains stack traces, secrets or provider internals. Unknown
fields in responses must be treated as forward compatible by consumers.

## Stable error codes

| Code | Status | Meaning |
| --- | --- | --- |
| `UNAUTHORIZED` | `401` | Missing, expired or invalid bearer token. |
| `INVALID_CURRENCY` | `422` | Currency codes are not three-letter ISO 4217. |
| `UNSUPPORTED_CURRENCY` | `422` | The provider does not support the currency pair. |
| `RATE_LIMITED` | `429` | The provider asked the service to retry later. |
| `PROVIDER_UNAVAILABLE` | `502` | Provider timeout, transport error or `5xx`. |
| `PROVIDER_INVALID_RESPONSE` | `502` | Provider payload is malformed. |
| `PROVIDER_NOT_CONFIGURED` | `503` | `EXCHANGE_PROVIDER_URL` is unset. |
| `PROVIDER_BUSY` | `503` | Provider concurrency limit reached. |
| `INTERNAL_ERROR` | `500` | Unexpected server error. |

Rate-limited and busy responses include `Retry-After`.