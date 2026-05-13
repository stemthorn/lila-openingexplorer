#!/bin/bash
set -euo pipefail

EXPLORER_PID=""
WRAPPER_PID=""
CADDY_PID=""

cleanup() {
  if [[ -n "${CADDY_PID}" ]]; then
    kill "${CADDY_PID}" 2>/dev/null || true
    wait "${CADDY_PID}" 2>/dev/null || true
  fi
  if [[ -n "${WRAPPER_PID}" ]]; then
    kill "${WRAPPER_PID}" 2>/dev/null || true
    wait "${WRAPPER_PID}" 2>/dev/null || true
  fi
  if [[ -n "${EXPLORER_PID}" ]]; then
    kill "${EXPLORER_PID}" 2>/dev/null || true
    wait "${EXPLORER_PID}" 2>/dev/null || true
  fi
}

trap 'cleanup; exit 0' TERM INT

echo "=== Starting lila-openingexplorer on 127.0.0.1:9002 ==="
DISABLE_BLACKLIST_UPDATE="${DISABLE_BLACKLIST_UPDATE:-1}" \
  /usr/local/bin/lila-openingexplorer --db /data/_db --bind 127.0.0.1:9002 &
EXPLORER_PID="${!}"

echo "=== Waiting for explorer /monitor ==="
for _ in $(seq 1 120); do
  if curl -sf "http://127.0.0.1:9002/monitor" >/dev/null 2>&1; then
    echo "→ Explorer is up."
    break
  fi
  sleep 1
done

if ! curl -sf "http://127.0.0.1:9002/monitor" >/dev/null 2>&1; then
  echo "ERROR: Explorer did not become ready on 127.0.0.1:9002/monitor" >&2
  cleanup
  exit 1
fi

echo "=== Starting Stockfish HTTP wrapper on 127.0.0.1:8082 ==="
/usr/local/bin/stockfish-http-wrapper --port 8082 --binary /usr/local/bin/stockfish &
WRAPPER_PID="${!}"

PORT_VALUE="${PORT:-8080}"
echo "=== Starting Caddy on port ${PORT_VALUE} ==="
/usr/local/bin/caddy run --config /etc/Caddyfile --adapter caddyfile &
CADDY_PID="${!}"

wait "${CADDY_PID}"
cleanup
