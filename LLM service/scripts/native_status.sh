#!/usr/bin/env bash

set -Eeuo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/native_common.sh"

status=0
if "$PG_BINDIR/pg_isready" -h 127.0.0.1 -p "$POSTGRES_PORT"; then
  echo "postgresql: running"
else
  echo "postgresql: stopped"
  status=1
fi
if curl -fsS --max-time 3 "http://127.0.0.1:$OLLAMA_PORT/api/tags" >/dev/null 2>&1; then
  echo "ollama:     running"
else
  echo "ollama:     stopped/disabled"
  [[ "$DIVE_LLM_ENABLED" == "true" || "$DIVE_LLM_ENABLED" == "1" ]] && status=1
fi
if curl -fsS --max-time 5 "http://127.0.0.1:$AI_API_PORT/health/live" >/dev/null 2>&1; then
  echo "api:        running at http://$AI_API_BIND:$AI_API_PORT"
  curl -fsS --max-time 10 "http://127.0.0.1:$AI_API_PORT/health/ready"
  echo
else
  echo "api:        stopped"
  status=1
fi
exit "$status"
