#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# shellcheck source=scripts/common.sh
. ./scripts/common.sh

BASE_URL="http://localhost:${EXCHANGE_PORT}"
ACCOUNT="0195ae95-5be7-7dd3-b35d-7a7d87c404fb"
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT

echo "Creating a local bearer token..."
TOKEN="$(
  "${COMPOSE[@]}" exec -T exchange \
    .venv/bin/python -m exchange.cli token --sub "${ACCOUNT}"
)"

if [[ -z "$TOKEN" ]]; then
  echo "The Exchange CLI did not return a token." >&2
  exit 1
fi

STATUS="$(
  curl --silent --show-error \
    -o "$WORK_DIR/rate.json" \
    -w '%{http_code}' \
    "${BASE_URL}/exchanges/USD/EUR" \
    -H "Authorization: Bearer ${TOKEN}"
)"

if [[ "$STATUS" != "200" ]]; then
  echo "Expected 200 from GET /exchanges/USD/EUR, received ${STATUS}." >&2
  cat "$WORK_DIR/rate.json" >&2 || true
  exit 1
fi

echo "Rate response: $(cat "$WORK_DIR/rate.json")"

"${COMPOSE[@]}" exec -T exchange .venv/bin/python - "${ACCOUNT}" "$(cat "$WORK_DIR/rate.json")" <<'PY'
import json
import re
import sys

payload = json.loads(sys.argv[2])

assert set(payload) == {"sell", "buy", "date", "id-account"}, payload
assert float(payload["sell"]) > 0, payload
assert float(payload["buy"]) > 0, payload
assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", payload["date"]), payload
assert payload["id-account"] == sys.argv[1], payload
print("Contract assertions passed.")
PY

INVALID_STATUS="$(
  curl --silent --show-error \
    -o /dev/null \
    -w '%{http_code}' \
    "${BASE_URL}/exchanges/XYZ/EUR" \
    -H "Authorization: Bearer ${TOKEN}"
)"
if [[ "$INVALID_STATUS" != "422" ]]; then
  echo "Expected 422 from GET /exchanges/XYZ/EUR, received ${INVALID_STATUS}." >&2
  exit 1
fi

UNSUPPORTED_STATUS="$(
  curl --silent --show-error \
    -o /dev/null \
    -w '%{http_code}' \
    "${BASE_URL}/exchanges/USD/EUR" \
    -H "Authorization: Bearer ${TOKEN}"
)"
if [[ "$UNSUPPORTED_STATUS" != "200" ]]; then
  echo "Expected 200 for a supported pair, received ${UNSUPPORTED_STATUS}." >&2
  exit 1
fi

echo "Exchange smoke test passed."
