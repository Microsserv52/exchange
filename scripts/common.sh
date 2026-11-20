ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -f .env ]]; then
  set -a
  . ./.env
  set +a
fi

EXCHANGE_PORT="${EXCHANGE_PORT:-8080}"
EXCHANGE_REDIS_PORT="${EXCHANGE_REDIS_PORT:-6381}"
EXCHANGE_PROVIDER_PORT="${EXCHANGE_PROVIDER_PORT:-8082}"
COMPOSE=(docker compose -f compose.yml)