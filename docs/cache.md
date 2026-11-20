---
icon: lucide/database-zap
---

# Cache and resilience

Caching is optional and disabled by default. The service is correct without
Redis; enabling the cache changes latency, not the API contract.

## Key and TTL

| Cache | Key | Example | TTL |
| --- | --- | --- | --- |
| `rate` | `exchange:rate:{EXCHANGE_PROVIDER_VERSION}:{FROM}:{TO}` | `exchange:rate:v1:USD:EUR` | `CACHE_TTL_SECONDS`, default 60 s |

## Single flight

Concurrent requests for the same pair share one provider call. The service holds
an `asyncio.Lock` per key and records a `stampede_wait` cache event when a
request waits for another in-flight request.

## Degraded behavior

- Cache operations never fail the request.
- A Redis outage is a cache miss; the request continues to the provider.
- Stale rates are never served. The contract has no stale-data allowance.
- When the cache is enabled and Redis is down, readiness reports `DEGRADED`.

## Measurements

| Metric | Meaning |
| --- | --- |
| `exchange_cache_events_total{event="hit"}` | Cache hits. |
| `exchange_cache_events_total{event="miss"}` | Cache misses. |
| `exchange_cache_events_total{event="set"}` | Successful writes. |
| `exchange_cache_events_total{event="error"}` | Cache operation failures. |
| `exchange_cache_events_total{event="stampede_wait"}` | Requests waiting on a shared provider call. |

## Enable the cache

```bash
CACHE_ENABLED=true CACHE_TTL_SECONDS=60 docker compose up --detach --build
```

Integration tests cover hit, miss, invalidation and Redis-unavailable behavior
before a release enables the flag.