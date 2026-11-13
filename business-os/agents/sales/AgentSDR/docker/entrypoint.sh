#!/bin/sh
# Image entrypoint: fills in what docker-compose.yml leaves implicit, refuses
# placeholder secrets on a public address, creates the schema in an empty
# database, then runs the real command.
set -eu

# Public origin: APP_URL is the one setting; the specific names win if set.
APP_URL="${APP_URL:-http://localhost:3000}"
APP_URL="${APP_URL%/}"
export BETTER_AUTH_URL="${BETTER_AUTH_URL:-$APP_URL}"
export NEXT_PUBLIC_APP_URL="${NEXT_PUBLIC_APP_URL:-$APP_URL}"
export OPENROUTER_SITE_URL="${OPENROUTER_SITE_URL:-$APP_URL}"

# Bundled database, unless DATABASE_URL points elsewhere.
checked="BETTER_AUTH_SECRET INTEGRATION_CREDENTIALS_KEY UNSUBSCRIBE_SECRET"
if [ -z "${DATABASE_URL:-}" ] && [ -n "${POSTGRES_PASSWORD:-}" ]; then
  checked="$checked POSTGRES_PASSWORD"
  export DATABASE_URL="postgres://agentsdr:${POSTGRES_PASSWORD}@db:5432/agentsdr"
  export DATABASE_SSL="${DATABASE_SSL:-disable}"
fi

# docker-compose.yml ships "changeme-…" placeholders so it starts as-is on a
# laptop. Anywhere else they would be public knowledge (anyone could forge a
# session), so refuse to start until they are replaced.
case "$BETTER_AUTH_URL" in
  http://localhost|http://localhost:*|http://127.0.0.1|http://127.0.0.1:*) ;;
  *)
    placeholders=""
    for name in $checked; do
      eval "value=\${$name:-}"
      case "$value" in changeme*) placeholders="$placeholders $name" ;; esac
    done
    if [ -n "$placeholders" ]; then
      echo "agentsdr: APP_URL is $BETTER_AUTH_URL but these still have their CHANGEME placeholder:$placeholders" >&2
      echo "agentsdr: set each to a random value (openssl rand -hex 32) in docker-compose.yml or .env." >&2
      exit 1
    fi
    ;;
esac

# Before the app server starts: create the schema if the database is empty.
# On an existing database this only reads the catalog and prints "already
# initialised" (it never upgrades one: migrations are in scripts/). If it
# fails (database unreachable, too old), the app does not start.
# AGENTSDR_SKIP_DB_SETUP=true skips it.
if [ "${1:-}" = "bun" ] && [ "${2:-}" = "server.js" ]; then
  case "${AGENTSDR_SKIP_DB_SETUP:-}" in
    1|true|TRUE|True|yes|on) echo "agentsdr: AGENTSDR_SKIP_DB_SETUP is set; database setup skipped" ;;
    *)
      if ! bun scripts/db/setup.ts --if-empty; then
        echo "agentsdr: database setup failed (see above); not starting. Check DATABASE_URL, or set AGENTSDR_SKIP_DB_SETUP=true to skip this step." >&2
        exit 1
      fi
      ;;
  esac
fi

exec "$@"
