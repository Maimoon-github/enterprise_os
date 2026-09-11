#!/usr/bin/env bash
# Run ruff and mypy.
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd -P)"

cd -- "$REPO_ROOT"

status=0

if command -v ruff >/dev/null 2>&1; then
    ruff check app tests || status=$?
else
    printf 'ruff not found, skipping lint\n' >&2
fi

if command -v mypy >/dev/null 2>&1; then
    mypy app || status=$?
else
    printf 'mypy not found, skipping typecheck\n' >&2
fi

exit "$status"
