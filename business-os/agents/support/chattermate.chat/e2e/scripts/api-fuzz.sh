#!/usr/bin/env bash
# Property-based checks of the whole API against its own OpenAPI schema
# (Schemathesis): every read endpoint, with generated ids, query strings and
# bodies, must answer without a server error. Runs against a stack already up
# (scripts/stack.sh up) whose org the setup project has created.
#
#   scripts/api-fuzz.sh            needs `st` on PATH (pip install schemathesis==4.31.0)
set -euo pipefail

E2E_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API="http://127.0.0.1:18000"
EMAIL="admin@e2e.example.com"          # src/env.ts seedUsers.admin
PASSWORD='E2e-Admin-Passw0rd!'

TOKEN="$(curl -fsS -X POST "$API/api/v1/users/login" --data-urlencode "username=$EMAIL" --data-urlencode "password=$PASSWORD" \
  | python3 -c 'import json, sys; print(json.load(sys.stdin)["access_token"])')"

mkdir -p "$E2E_DIR/test-results"
# Reads only for now: writes would also need cleanup between examples. Signing out
# would revoke the token mid-run.
exec st run "$API/openapi.json" \
  -H "Authorization: Bearer $TOKEN" \
  --checks not_a_server_error \
  --include-method GET \
  --exclude-path-regex '/users/(logout|me)$' \
  -n 5 \
  --report junit --report-junit-path "$E2E_DIR/test-results/api-fuzz.xml"
