#!/bin/bash
set -e

echo "=== Setting up Stockfish ==="
mkdir -p /data/stockfish
STOCKFISH_BIN="/data/stockfish/stockfish"

if [ ! -f "$STOCKFISH_BIN" ] || [ ! -x "$STOCKFISH_BIN" ]; then
  echo "=== Downloading Stockfish ==="
  curl -L -o /tmp/sf.tar.gz \
    https://github.com/official-stockfish/Stockfish/releases/latest/download/stockfish-ubuntu-x86-64-avx2.tar.gz
  tar -xzf /tmp/sf.tar.gz -C /data/stockfish --strip-components=1
  chmod +x "$STOCKFISH_BIN"
  rm -f /tmp/sf.tar.gz
  echo "=== Stockfish installed successfully ==="
else
  echo "=== Stockfish already present ==="
fi

echo "=== Starting lila-openingexplorer ==="
exec lila-openingexplorer --db /data/_db --bind 0.0.0.0:${PORT:-8080}
