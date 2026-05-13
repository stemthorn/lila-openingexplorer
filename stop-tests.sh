#!/bin/bash
# 1. Stop the container (if it's still running)
docker stop lila-test

# 2. Remove the container
docker rm -f lila-test

# 3. Check if anything is still running on port 8080
docker ps | grep 8080

# 4. (Optional) Kill anything still listening on port 8080
lsof -ti:8080 | xargs kill -9 2>/dev/null || true
