#!/usr/bin/env bash
#
# scripts/run_dev_server.sh — start the API with uvicorn's auto-reloading
# development server. Not for production use (see deployment tooling for
# that); this script only ever targets local iteration.
#
# Usage: scripts/run_dev_server.sh [HOST] [PORT]

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd -P)"
readonly SCRIPT_DIR
# shellcheck source=SCRIPTDIR/lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"

main() {
    local host="${1:-127.0.0.1}"
    local port="${2:-8000}"

    ensure_venv_active
    require_cmd uvicorn "run scripts/bootstrap.sh first"

    local repo_root_dir
    repo_root_dir="$(repo_root)"
    cd -- "${repo_root_dir}"

    if [[ ! -f "${repo_root_dir}/.env" ]]; then
        log_warn "No .env file found; the app will fall back to built-in defaults."
    fi

    log_info "Starting dev server on ${host}:${port} (auto-reload enabled)"
    uvicorn app.main:app --reload --host "${host}" --port "${port}"
}

main "$@"
