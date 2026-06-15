#!/usr/bin/env bash
# Build (if needed) and run the FinAlly container. Idempotent.
set -euo pipefail

IMAGE="finally"
CONTAINER="finally"
VOLUME="finally-data"
PORT=8000

cd "$(dirname "$0")/.."

BUILD=false
if [[ "${1:-}" == "--build" ]]; then
  BUILD=true
fi

if $BUILD || ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "Building image $IMAGE..."
  docker build -t "$IMAGE" .
fi

# Remove any existing container so this is safe to re-run.
docker rm -f "$CONTAINER" >/dev/null 2>&1 || true

echo "Starting container $CONTAINER..."
docker run -d \
  --name "$CONTAINER" \
  -p "$PORT:8000" \
  --env-file .env \
  -v "$VOLUME:/data" \
  "$IMAGE"

echo "FinAlly is running at http://localhost:$PORT"
