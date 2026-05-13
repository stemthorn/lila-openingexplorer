#!/bin/bash
docker run --platform linux/amd64 \
  -p 8080:8080 \
  -v $(pwd)/data:/data \
  -e PORT=8080 \
  --name lila-test \
  --rm \
  lila-openingexplorer:local
