#!/usr/bin/env bash
set -euo pipefail

if [[ -x /Users/postgres/bin/initdb && -x /Users/postgres/bin/pg_ctl \
  && -x /Users/postgres/bin/postgres ]]; then
  pg_bin="/Users/postgres/bin/"
elif command -v initdb >/dev/null 2>&1 && command -v pg_ctl >/dev/null 2>&1 \
  && [[ -x "$(dirname "$(command -v initdb)")/postgres" ]]; then
  pg_bin="$(dirname "$(command -v initdb)")/"
else
  echo "PostgreSQL server tools (initdb and pg_ctl) are required" >&2
  exit 1
fi

fixture_cluster_dir=$(mktemp -d /tmp/agentsdr-webhook-fixture.XXXXXX)
fixture_port=$((56000 + ($$ % 1000)))

cleanup() {
  "${pg_bin}pg_ctl" -D "$fixture_cluster_dir" -m fast -w stop >/dev/null 2>&1 || true
  case "$fixture_cluster_dir" in
    /tmp/agentsdr-webhook-fixture.*) rm -rf -- "$fixture_cluster_dir" ;;
    *) echo "Refusing to remove unexpected fixture path: $fixture_cluster_dir" >&2 ;;
  esac
}
trap cleanup EXIT

"${pg_bin}initdb" -D "$fixture_cluster_dir" -A trust -U postgres >/dev/null
"${pg_bin}pg_ctl" -D "$fixture_cluster_dir" -o "-h 127.0.0.1 -p $fixture_port" -w start >/dev/null
"${pg_bin}createdb" -h 127.0.0.1 -p "$fixture_port" -U postgres agentsdr_webhook_fixture

fixture_database_url="postgresql://postgres@127.0.0.1:$fixture_port/agentsdr_webhook_fixture?sslmode=disable"
"${pg_bin}psql" "$fixture_database_url" -X -v ON_ERROR_STOP=1 \
  -f tests/fixtures/legacy-people-migration.sql >/dev/null
DATABASE_URL="$fixture_database_url" DATABASE_SSL=disable \
  bun --no-env-file --conditions=react-server scripts/create-lead-tables.ts --apply >/dev/null
DATABASE_URL="$fixture_database_url" DATABASE_SSL=disable \
  bun --no-env-file --conditions=react-server scripts/test-linkedin-webhook-inbox.ts
