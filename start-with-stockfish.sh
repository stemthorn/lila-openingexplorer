#!/bin/bash
set -euo pipefail

echo "=== Stockfish setup starting (safe - not touching _db) ==="

# Ensure curl is available
if ! command -v curl >/dev/null 2>&1; then
  echo "curl not found - installing..."
  apt-get update && apt-get install -y --no-install-recommends curl ca-certificates
fi

mkdir -p /data/stockfish
STOCKFISH_BIN="/data/stockfish/stockfish"

if [ ! -f "$STOCKFISH_BIN" ] || [ ! -x "$STOCKFISH_BIN" ]; then
  echo "=== Downloading Stockfish (AVX2) ==="

  curl -L -o /tmp/stockfish.tar \
    https://github.com/official-stockfish/Stockfish/releases/latest/download/stockfish-ubuntu-x86-64-avx2.tar

  # Extract and handle the subdirectory structure
  tar -xf /tmp/stockfish.tar -C /data/stockfish --strip-components=1

  # The binary is usually named stockfish-ubuntu-x86-64-avx2 or similar — rename it
  if [ -f /data/stockfish/stockfish-ubuntu-x86-64-avx2 ]; then
    mv /data/stockfish/stockfish-ubuntu-x86-64-avx2 "$STOCKFISH_BIN"
  elif [ -f /data/stockfish/stockfish ]; then
    mv /data/stockfish/stockfish "$STOCKFISH_BIN"
  fi

  chmod +x "$STOCKFISH_BIN"
  rm -f /tmp/stockfish.tar

  echo "=== Stockfish installed successfully ==="
else
  echo "=== Stockfish already present on persistent disk ==="
fi

echo "=== Starting lila-openingexplorer (using existing /data/_db) ==="
exec lila-openingexplorer --db /data/_db --bind 0.0.0.0:${PORT:-8080}
