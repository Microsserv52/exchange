---
icon: lucide/database
---

# Database

Exchange has no database. It owns only the HTTP contract and the provider
integration. Other platform services call Exchange; Exchange never calls them.

## Cache persistence

The optional cache lives in Redis. Compose enables append-only persistence on
a named volume, so unexpired entries can survive restarts. Entries still expire
according to their TTL: a cache miss is a provider call, and the service never
serves expired data.

## Retention

Rates are not stored permanently. The cache TTL is bounded by
`CACHE_TTL_SECONDS`, and provider responses are fetched on demand.

## Indexes

No indexes exist. Exchange is stateless except for the in-process lock map used
to prevent provider stampedes.
