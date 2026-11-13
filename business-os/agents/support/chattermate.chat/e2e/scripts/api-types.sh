#!/usr/bin/env bash
# Regenerates src/api/schema.d.ts — TypeScript types for every backend route and
# payload — from the OSS backend's own OpenAPI schema, so a renamed route or field
# fails `npm run typecheck` here instead of a test at runtime.
#
#   scripts/api-types.sh          write src/api/schema.d.ts
#   scripts/api-types.sh --check  fail if it is out of date (CI)
set -euo pipefail

E2E_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_DIR="$(cd "$E2E_DIR/.." && pwd)"
if [[ -z "${E2E_PYTHON:-}" ]]; then
  if [[ -x "$REPO_DIR/backend/venv/bin/python" ]]; then E2E_PYTHON="$REPO_DIR/backend/venv/bin/python"; else E2E_PYTHON="python3"; fi
fi
work="$(mktemp -d)"; trap 'rm -rf "$work"' EXIT

# The OSS edition's schema: the public suite never types enterprise routes.
(cd "$REPO_DIR/backend" && ENV_FILE="$E2E_DIR/.env.e2e" NO_ENTERPRISE=1 \
  DATABASE_URL="postgresql+psycopg://openapi@127.0.0.1:1/none" \
  "$E2E_PYTHON" -c 'import json, sys, app.main; from app.core.application import app; json.dump(app.openapi(), open(sys.argv[1], "w"))' \
  "$work/openapi.json" >/dev/null 2>&1)

"$E2E_DIR/node_modules/.bin/openapi-typescript" "$work/openapi.json" -o "$work/schema.d.ts" >/dev/null
if [[ "${1:-}" == "--check" ]]; then
  diff -q "$work/schema.d.ts" "$E2E_DIR/src/api/schema.d.ts" >/dev/null \
    || { echo "src/api/schema.d.ts is out of date: run e2e/scripts/api-types.sh and commit it" >&2; exit 1; }
else
  cp "$work/schema.d.ts" "$E2E_DIR/src/api/schema.d.ts"
fi
