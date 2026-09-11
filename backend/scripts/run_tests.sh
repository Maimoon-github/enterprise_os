#!/usr/bin/env bash
#
# scripts/run_tests.sh — run the full pytest suite from a known-good
# environment. Any extra arguments are passed through to pytest, e.g.:
#   scripts/run_tests.sh tests/unit -k policy

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd -P)"
readonly SCRIPT_DIR
# shellcheck source=SCRIPTDIR/lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"

main() {
    ensure_venv_active
    require_cmd pytest "run scripts/bootstrap.sh first"

    cd -- "$(repo_root)"
    log_info "Running pytest"
    pytest "$@"
}

main "$@"
