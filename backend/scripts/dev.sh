#!/usr/bin/env bash
# Run the development API server.
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd -P)"

cd -- "$REPO_ROOT"

if ! python -c 'import uvicorn' >/dev/null 2>&1; then
    printf 'uvicorn not installed. Run: pip install -e ".[dev]"\n' >&2
    exit 1
fi

exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${BACKEND_PORT:-8000}" --reload
