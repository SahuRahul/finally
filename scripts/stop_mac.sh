#!/usr/bin/env bash
# Stop and remove the FinAlly container. Keeps the data volume. Idempotent.
set -euo pipefail

CONTAINER="finally"

docker rm -f "$CONTAINER" >/dev/null 2>&1 && \
  echo "Stopped and removed container $CONTAINER (data volume preserved)." || \
  echo "Container $CONTAINER is not running."
