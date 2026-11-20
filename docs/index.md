---
icon: lucide/network
---

# Exchange

Currency conversion for the [Microsserv52 platform](https://github.com/Microsserv52/platform).
The service is implemented with Python 3.14, `uv` and FastAPI, validates ISO 4217
currencies, calls a configurable third-party provider through an adapter, optionally
caches rates in Redis and returns the stable platform response.

The [canonical HTTP contract lives in
Microsserv52/exchange-interface](https://github.com/Microsserv52/exchange-interface).
Provider payloads are never part of the platform contract.

## Quick start

The supported clean-machine path is fully containerized. It requires Git, Docker and
Docker Compose v2; it does not require host Python, `uv` or Redis.

```bash
git clone --recurse-submodules https://github.com/Microsserv52/exchange.git
cd exchange
./scripts/bootstrap.sh
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

`GET /exchanges/{from}/{to}` requires an HS256 bearer JWT whose `sub` is the account UUID.

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

The Gateway routes `/exchanges/**` to this service.

See [API and errors](api.md) for the full reference.

## Links

- [Microsserv52 organization](https://github.com/Microsserv52)
- [Platform repository](https://github.com/Microsserv52/platform)
- [Published platform documentation](https://microsserv52.github.io/platform/)
- [Exchange service repository](https://github.com/Microsserv52/exchange)
- [Exchange interface repository](https://github.com/Microsserv52/exchange-interface)
- [Exchange interface documentation](https://microsserv52.github.io/exchange-interface/)