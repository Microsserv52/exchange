---
icon: lucide/container
---

# Kubernetes and rollback

## Deployment

Deploy the immutable image `ghcr.io/microsserv52/exchange:sha-<full-commit-sha>`.
Never use `latest` in production.

Required environment variables:

```yaml
env:
  - name: EXCHANGE_PROVIDER_URL
    value: "https://rates.example.com"
  - name: EXCHANGE_PROVIDER_API_KEY
    valueFrom:
      secretKeyRef:
        name: exchange-provider
        key: api-key
  - name: JWT_SECRET
    valueFrom:
      secretKeyRef:
        name: platform-jwt
        key: secret
  - name: JWT_ISSUER
    value: "https://auth.example.com"
  - name: JWT_AUDIENCE
    value: "exchange"
  - name: CACHE_ENABLED
    value: "true"
  - name: CACHE_REDIS_URL
    valueFrom:
      secretKeyRef:
        name: exchange-redis
        key: url
```

## Probes

```yaml
livenessProbe:
  httpGet:
    path: /health/live
    port: 8080
readinessProbe:
  httpGet:
    path: /health/ready
    port: 8080
```

Readiness turns `DOWN` when the provider is unconfigured, and `DEGRADED` when
the cache is enabled but Redis is unreachable.

## Scaling

- The service is stateless; horizontal scaling is safe.
- `EXCHANGE_PROVIDER_MAX_CONCURRENCY` bounds per-instance provider load. Set it
  below the provider's per-instance rate limit divided by the expected replica
  count.
- Redis is shared; use a single Redis instance or a managed cache.

## Rollback

Roll back by pointing the deployment at the previous immutable SHA image. The
contract is stable; a rollback does not require a database migration.

## Observability

- Scrape `/metrics` with Prometheus.
- Ship structured logs to the platform log sink.
- Alert on the conditions documented in [Observability](observability.md).