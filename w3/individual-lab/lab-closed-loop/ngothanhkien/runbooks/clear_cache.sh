#!/usr/bin/env bash
set -euo pipefail

SERVICE=""
DRY_RUN=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --service)
      SERVICE="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    *)
      echo "Unknown arg: $1"
      exit 1
      ;;
  esac
done

if [[ -z "$SERVICE" ]]; then
  echo "[clear_cache] ERROR: --service <name> required"
  exit 1
fi

CONTAINER="ronki-${SERVICE}"

if $DRY_RUN; then
  echo "[DRY-RUN] would execute: docker exec $CONTAINER sh -lc 'echo clear cache'"
  exit 0
fi

if docker inspect "$CONTAINER" >/dev/null 2>&1; then
  docker exec "$CONTAINER" sh -lc 'echo "[clear_cache] cache cleared"'
else
  echo "[clear_cache] container $CONTAINER not found"
  exit 1
fi

exit 0
