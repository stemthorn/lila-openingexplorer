#!/usr/bin/env bash
# Go wrapper is built inside the Dockerfile. Run from this directory.
set -euo pipefail
cd "$(dirname "$0")"

docker buildx build --platform linux/amd64 \
  -t lila-openingexplorer:local .
