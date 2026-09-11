#!/usr/bin/env bash
# Run the pytest suite.
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd -P)"

cd -- "$REPO_ROOT"

if ! python -c 'import pytest' >/dev/null 2>&1; then
    printf 'pytest not installed. Run: pip install -e ".[dev]"\n' >&2
    exit 1
fi

exec python -m pytest "$@"
