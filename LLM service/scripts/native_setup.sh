#!/usr/bin/env bash

set -Eeuo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/native_common.sh"

if [[ ! -x "$PG_BINDIR/postgres" || ! -x "$PG_BINDIR/initdb" ]]; then
  echo "PostgreSQL server is missing. Install: sudo apt-get install -y postgresql postgresql-client" >&2
  exit 1
fi
if ! command -v ollama >/dev/null 2>&1; then
  echo "Ollama is missing. Install the native Linux binary from https://ollama.com/download" >&2
  exit 1
fi
installed_ollama_version="$(ollama --version 2>&1 | sed -n 's/.*version is //p; s/.*version //p' | tail -1)"
if [[ "$installed_ollama_version" != "$OLLAMA_NATIVE_VERSION" ]]; then
  echo "Ollama $OLLAMA_NATIVE_VERSION is required for NVIDIA driver 535; installed: ${installed_ollama_version:-unknown}" >&2
  exit 1
fi

if [[ ! -x "$PYTHON_BIN" ]]; then
  python3 -m venv "$PROJECT_ROOT/.venv"
fi
if "$PYTHON_BIN" -c 'import sys; raise SystemExit(sys.version_info < (3, 11))'; then
  requirements_file="$PROJECT_ROOT/requirements.lock"
else
  # requirements.lock was produced by the Python 3.12 Docker image and contains
  # packages (for example contourpy 1.3.3) that do not support Ubuntu 22.04's
  # default Python 3.10.
  requirements_file="$PROJECT_ROOT/requirements.txt"
fi
"$PROJECT_ROOT/.venv/bin/pip" install -r "$requirements_file"

if [[ ! -s "$NATIVE_PGDATA/PG_VERSION" ]]; then
  mkdir -p "$NATIVE_PGDATA"
  "$PG_BINDIR/initdb" \
    --pgdata="$NATIVE_PGDATA" \
    --username=postgres \
    --encoding=UTF8 \
    --auth-local=trust \
    --auth-host=scram-sha-256 \
    --no-instructions
fi

cat > "$PROJECT_ROOT/.env.native.example" <<'EOF'
# Optional native-runtime overrides. Copy to .env.native when needed.
NATIVE_RUNTIME_DIR=
AI_API_BIND=0.0.0.0
AI_API_PORT=8000
POSTGRES_PORT=5432
OLLAMA_PORT=11434
OLLAMA_NATIVE_VERSION=0.11.10
DIVE_LLM_ENABLED=true
EOF

echo "Native runtime setup complete: $NATIVE_RUNTIME_DIR"
