---
icon: lucide/history
---

# Changelog and versioning

All notable changes are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/) and this project adheres to
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Initial service implementation (Python 3.14, `uv`, FastAPI).
- Provider adapter with retry, timeout and payload normalization.
- Optional Redis cache with single-flight stampede protection.
- Contract endpoints: `GET /exchanges/{from}/{to}`, health, metrics.
- Deterministic provider mock for local and CI testing.
- Contract test snapshots from exchange-interface.

## Versioning

- MAJOR: removed fields, changed status codes, renamed endpoints.
- MINOR: additive optional fields, new error codes.
- PATCH: bug fixes, documentation, CI improvements.

## Release process

1. Ensure `main` is clean (format, lint, type-check, tests, coverage, CodeQL, Compose, container).
2. Tag `vX.Y.Z` on `main`.
3. CI publishes `ghcr.io/microsserv52/exchange:vX.Y.Z` and `sha-<full-sha>`.
4. Kubernetes deployments use an immutable digest or `sha-` tag, never `latest`.