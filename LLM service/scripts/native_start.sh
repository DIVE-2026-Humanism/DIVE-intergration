#!/usr/bin/env bash

set -Eeuo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/native_common.sh"

if [[ ! -x "$PYTHON_BIN" || ! -s "$NATIVE_PGDATA/PG_VERSION" ]]; then
  "$SCRIPT_DIR/native_setup.sh"
fi

cd "$PROJECT_ROOT"

if ! "$PG_BINDIR/pg_isready" -h "$NATIVE_PGSOCKET" -p "$POSTGRES_PORT" >/dev/null 2>&1; then
  "$PG_BINDIR/pg_ctl" \
    --pgdata="$NATIVE_PGDATA" \
    --log="$NATIVE_LOG_DIR/postgres.log" \
    --options="-h 127.0.0.1 -p $POSTGRES_PORT -k $NATIVE_PGSOCKET" \
    --wait start
fi
"$PYTHON_BIN" "$SCRIPT_DIR/native_bootstrap_db.py"

if [[ "$DIVE_LLM_ENABLED" == "true" || "$DIVE_LLM_ENABLED" == "1" ]]; then
  if ! curl -fsS --max-time 2 "http://127.0.0.1:$OLLAMA_PORT/api/tags" >/dev/null 2>&1; then
    nohup setsid env \
      OLLAMA_HOST="127.0.0.1:$OLLAMA_PORT" \
      OLLAMA_MODELS="$NATIVE_OLLAMA_MODELS" \
      ollama serve >"$NATIVE_LOG_DIR/ollama.log" 2>&1 &
    echo "$!" > "$NATIVE_RUN_DIR/ollama.pid"
  fi
  if ! wait_http "http://127.0.0.1:$OLLAMA_PORT/api/tags" 60; then
    echo "Ollama failed to start; see $NATIVE_LOG_DIR/ollama.log" >&2
    exit 1
  fi
  export OLLAMA_HOST="127.0.0.1:$OLLAMA_PORT"
  export OLLAMA_MODELS="$NATIVE_OLLAMA_MODELS"
  if ! ollama list | awk 'NR > 1 {print $1}' | grep -Fxq "$OLLAMA_MODEL"; then
    ollama pull "$OLLAMA_BASE_MODEL"
    ollama create "$OLLAMA_MODEL" -f "$PROJECT_ROOT/models/Modelfile"
  fi
fi

export DIVE_DATABASE_URL="$("$PYTHON_BIN" -c '
import os
from urllib.parse import quote
user = quote(os.environ["POSTGRES_USER"], safe="")
password = quote(os.environ["POSTGRES_PASSWORD"], safe="")
database = quote(os.environ["POSTGRES_DB"], safe="")
port = os.environ["POSTGRES_PORT"]
print(f"postgresql://{user}:{password}@127.0.0.1:{port}/{database}")
')"
export DIVE_AUTO_INGEST=true
export OLLAMA_BASE_URL="http://127.0.0.1:$OLLAMA_PORT"
export OLLAMA_MODEL DIVE_CORS_ORIGINS DIVE_LLM_ENABLED

if ! pid_is_running "$NATIVE_RUN_DIR/api.pid"; then
  nohup setsid "$PYTHON_BIN" -m uvicorn src.api:app \
    --host "$AI_API_BIND" --port "$AI_API_PORT" \
    >"$NATIVE_LOG_DIR/api.log" 2>&1 &
  echo "$!" > "$NATIVE_RUN_DIR/api.pid"
fi
if ! wait_http "http://127.0.0.1:$AI_API_PORT/health/live" 90; then
  echo "API failed to start; see $NATIVE_LOG_DIR/api.log" >&2
  exit 1
fi

echo "Native services started."
"$SCRIPT_DIR/native_status.sh"
