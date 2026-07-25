#!/usr/bin/env bash

set -Eeuo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/native_common.sh"

stop_pid_file() {
  local name="$1" pid_file="$2"
  if pid_is_running "$pid_file"; then
    local pid
    pid="$(cat "$pid_file")"
    kill "$pid"
    for _ in {1..20}; do
      kill -0 "$pid" 2>/dev/null || break
      sleep 0.25
    done
    kill -0 "$pid" 2>/dev/null && kill -KILL "$pid"
    echo "Stopped $name (PID $pid)"
  fi
  rm -f "$pid_file"
}

stop_pid_file api "$NATIVE_RUN_DIR/api.pid"
stop_pid_file ollama "$NATIVE_RUN_DIR/ollama.pid"
if [[ -x "$PG_BINDIR/pg_ctl" && -s "$NATIVE_PGDATA/PG_VERSION" ]] && \
   "$PG_BINDIR/pg_ctl" --pgdata="$NATIVE_PGDATA" status >/dev/null 2>&1; then
  "$PG_BINDIR/pg_ctl" --pgdata="$NATIVE_PGDATA" --wait --mode=fast stop
  echo "Stopped PostgreSQL"
fi
