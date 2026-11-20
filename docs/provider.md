---
icon: lucide/settings
---

# Provider adapter

`exchange.providers.http.HttpExchangeProvider` expects:

```http
GET {EXCHANGE_PROVIDER_URL}/latest?base=USD&symbols=EUR
Authorization: Bearer <EXCHANGE_PROVIDER_API_KEY>
Accept: application/json
```

The response must contain a `rates` object. Each entry may be a number (mid rate) or
an object with `bid`/`ask` or `buy`/`sell`. Optional timestamps are read from
`timestamp`, `time_last_update_unix`, `date`, `observed_at` or `time`. The adapter
normalizes the payload and never exposes provider fields directly.

## Failure handling

| Provider response | Exchange outcome |
| --- | --- |
| `200` with valid rates | Rate returned normally. |
| `400`, `404`, `422` from provider | `422 UNSUPPORTED_CURRENCY`. |
| `401`, `403` from provider | `503 PROVIDER_NOT_CONFIGURED`. |
| `429` from provider | `429 RATE_LIMITED` with `Retry-After`. |
| `5xx` from provider | `502 PROVIDER_UNAVAILABLE`. |
| Timeout / connection error | Retry up to `EXCHANGE_PROVIDER_RETRIES` times. Final failure is `502`. |

## Idempotency

Rate lookups are read-only and safe to retry. A later request may observe a
new rate, even when it uses the same currency pair.

## Concurrency

Per-instance concurrency is bounded by `EXCHANGE_PROVIDER_MAX_CONCURRENCY`. When
the limit is reached, new requests return `503 PROVIDER_BUSY` with a
`Retry-After` header.

## A replacement provider

Must implement
`exchange.providers.base.ExchangeProvider`:

```python
class ExchangeProvider(Protocol):
    def is_configured(self) -> bool: ...

    async def get_rate(self, source: str, target: str) -> ProviderRate: ...

    async def close(self) -> None: ...
```

Only timeouts, transport errors and `408`/`425`/`5xx` responses are retried.
`4xx` responses are not retried. `400`, `404` and `422` mean the currency is
unsupported by the provider. `401`/`403` mean the provider is misconfigured.
`429` returns `RATE_LIMITED` with `Retry-After`.