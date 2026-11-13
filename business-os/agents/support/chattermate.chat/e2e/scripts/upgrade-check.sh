#!/usr/bin/env bash
# Migrations must upgrade the database a deployment already has, not only build
# a fresh one (the e2e template is always built at HEAD). This builds a database
# with the last release's migrations, upgrades it with HEAD's, and checks the
# result is the same schema as a database built fresh at HEAD.
#
#   scripts/upgrade-check.sh [base-ref]     default: the latest v* tag
#
# Same knobs as stack.sh: E2E_PG_URL, E2E_PYTHON. OSS edition (NO_ENTERPRISE=1).
# E2E_PG_DUMP: a pg_dump matching the server's major version (default: pg_dump).
set -euo pipefail

E2E_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_DIR="$(cd "$E2E_DIR/.." && pwd)"
PG_URL="${E2E_PG_URL:-postgresql://${USER}@127.0.0.1:5432}"; PG_URL="${PG_URL%/}"
DB_NAME="chattermate_upgrade_e2e"
FRESH_DB="chattermate_fresh_e2e"
BASE_REF="${1:-$(git -C "$REPO_DIR" describe --tags --abbrev=0 --match 'v*')}"
if [[ -z "${E2E_PYTHON:-}" ]]; then
  if [[ -x "$REPO_DIR/backend/venv/bin/python" ]]; then E2E_PYTHON="$REPO_DIR/backend/venv/bin/python"; else E2E_PYTHON="python3"; fi
fi

log() { printf '\033[36m[upgrade]\033[0m %s\n' "$*" >&2; }
for db in "$DB_NAME" "$FRESH_DB"; do [[ "$db" == *_e2e ]] || { echo "refusing to manage $db" >&2; exit 1; }; done

psql_admin() { psql "$PG_URL/postgres" -v ON_ERROR_STOP=1 -qtA "$@"; }
base="${PG_URL#postgres://}"; base="${base#postgresql://}"
db_url() { echo "postgresql+psycopg://$base/$1"; }

# Settings come from the e2e env file: HEAD reads it through ENV_FILE, and the old
# release gets a copy as its backend/.env (it predates ENV_FILE).
export ENV_FILE="$E2E_DIR/.env.e2e" NO_ENTERPRISE=1

work="$(mktemp -d)"
cleanup() {
  git -C "$REPO_DIR" worktree remove --force "$work/base" >/dev/null 2>&1 || true
  rm -rf "$work"
  for db in "$DB_NAME" "$FRESH_DB"; do psql_admin -c "DROP DATABASE IF EXISTS $db" >/dev/null 2>&1 || true; done
}
trap cleanup EXIT

for db in "$DB_NAME" "$FRESH_DB"; do
  psql_admin -c "DROP DATABASE IF EXISTS $db"
  psql_admin -c "CREATE DATABASE $db"
  psql "$PG_URL/$db" -v ON_ERROR_STOP=1 -qtA -c "CREATE EXTENSION IF NOT EXISTS vector"
done

log "building the schema at $BASE_REF"
git -C "$REPO_DIR" worktree add --detach "$work/base" "$BASE_REF" >/dev/null 2>&1
cp "$E2E_DIR/.env.e2e" "$work/base/backend/.env"
(cd "$work/base/backend" && DATABASE_URL="$(db_url "$DB_NAME")" "$E2E_PYTHON" -m alembic upgrade head)

log "upgrading to $(git -C "$REPO_DIR" rev-parse --short HEAD), and building the same fresh"
cd "$REPO_DIR/backend"
DATABASE_URL="$(db_url "$DB_NAME")" "$E2E_PYTHON" -m alembic upgrade head
DATABASE_URL="$(db_url "$FRESH_DB")" "$E2E_PYTHON" -m alembic upgrade head

# Schema only, without the noise that legitimately differs (dump header, ownership).
# Written to files first, so a failed dump fails the check instead of diffing nothing.
schema() {
  "${E2E_PG_DUMP:-pg_dump}" --schema-only --no-owner --no-privileges --no-comments "$PG_URL/$1" >"$work/$1.raw.sql"
  grep -vE '^(--|SET |SELECT pg_catalog\.set_config|\\(un)?restrict )' "$work/$1.raw.sql" | sed '/^$/d' >"$work/$1.sql"
  [[ -s "$work/$1.sql" ]] || { echo "empty schema dump for $1" >&2; exit 1; }
}
schema "$FRESH_DB"
schema "$DB_NAME"
if ! diff -u "$work/$FRESH_DB.sql" "$work/$DB_NAME.sql" >"$work/schema.diff"; then
  echo "an upgraded database differs from a fresh one at HEAD (fresh → upgraded):" >&2
  cat "$work/schema.diff" >&2
  exit 1
fi
log "ok: $BASE_REF → HEAD upgrades to exactly the schema a fresh install gets"
