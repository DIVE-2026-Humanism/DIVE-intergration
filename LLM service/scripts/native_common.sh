#!/usr/bin/env bash

set -Eeuo pipefail

NATIVE_SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$NATIVE_SCRIPT_DIR/.." && pwd)"

if [[ -f "$PROJECT_ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$PROJECT_ROOT/.env"
  set +a
fi
if [[ -f "$PROJECT_ROOT/.env.native" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$PROJECT_ROOT/.env.native"
  set +a
fi

NATIVE_RUNTIME_DIR="${NATIVE_RUNTIME_DIR:-$PROJECT_ROOT/.native}"
NATIVE_RUN_DIR="$NATIVE_RUNTIME_DIR/run"
NATIVE_LOG_DIR="$NATIVE_RUNTIME_DIR/logs"
NATIVE_PGDATA="$NATIVE_RUNTIME_DIR/postgres"
NATIVE_OLLAMA_MODELS="$NATIVE_RUNTIME_DIR/ollama/models"
NATIVE_PGSOCKET="${NATIVE_PGSOCKET:-/tmp/dive-native-pg-$(id -u)}"

POSTGRES_DB="${POSTGRES_DB:-dive}"
POSTGRES_USER="${POSTGRES_USER:-dive}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-change-this-postgres-password}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
OLLAMA_PORT="${OLLAMA_PORT:-11434}"
OLLAMA_NATIVE_VERSION="${OLLAMA_NATIVE_VERSION:-0.11.10}"
OLLAMA_BASE_MODEL="${OLLAMA_BASE_MODEL:-qwen3:8b}"
OLLAMA_MODEL="${OLLAMA_MODEL:-dive-qwen3:8b}"
AI_API_BIND="${AI_API_BIND:-0.0.0.0}"
AI_API_PORT="${AI_API_PORT:-8000}"
DIVE_CORS_ORIGINS="${DIVE_CORS_ORIGINS:-*}"
DIVE_LLM_ENABLED="${DIVE_LLM_ENABLED:-true}"
PYTHON_BIN="$PROJECT_ROOT/.venv/bin/python"

PG_BINDIR="${PG_BINDIR:-$(pg_config --bindir 2>/dev/null || true)}"
if [[ -z "$PG_BINDIR" && -x /usr/lib/postgresql/14/bin/postgres ]]; then
  PG_BINDIR=/usr/lib/postgresql/14/bin
fi

mkdir -p "$NATIVE_RUN_DIR" "$NATIVE_LOG_DIR" "$NATIVE_OLLAMA_MODELS" "$NATIVE_PGSOCKET"

pid_is_running() {
  local pid_file="$1"
  [[ -s "$pid_file" ]] || return 1
  local pid
  pid="$(cat "$pid_file")"
  [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null
}

wait_http() {
  local url="$1" attempts="${2:-60}"
  for ((i = 1; i <= attempts; i++)); do
    if curl -fsS --max-time 2 "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  return 1
}

export PROJECT_ROOT NATIVE_RUNTIME_DIR NATIVE_RUN_DIR NATIVE_LOG_DIR
export NATIVE_PGDATA NATIVE_OLLAMA_MODELS NATIVE_PGSOCKET PG_BINDIR PYTHON_BIN
export POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD POSTGRES_PORT
export OLLAMA_PORT OLLAMA_NATIVE_VERSION OLLAMA_BASE_MODEL OLLAMA_MODEL AI_API_BIND AI_API_PORT
export DIVE_CORS_ORIGINS DIVE_LLM_ENABLED
