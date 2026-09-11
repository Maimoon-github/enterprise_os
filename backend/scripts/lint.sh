#!/usr/bin/env bash
#
# scripts/lint.sh — run every static check the project relies on: ruff and
# mypy over the Python sources, and shellcheck over every script in
# scripts/. Exits non-zero if any check fails, after running all of them,
# so a single invocation reports every problem instead of stopping at the
# first one.

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd -P)"
readonly SCRIPT_DIR
# shellcheck source=SCRIPTDIR/lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"

main() {
    ensure_venv_active
    require_cmd ruff "run scripts/bootstrap.sh first"
    require_cmd mypy "run scripts/bootstrap.sh first"

    local repo_root_dir
    repo_root_dir="$(repo_root)"
    cd -- "${repo_root_dir}"

    local failed=0

    log_info "Running ruff"
    if ! ruff check app tests; then
        failed=1
    fi

    log_info "Running mypy"
    if ! mypy app; then
        failed=1
    fi

    if command -v shellcheck >/dev/null 2>&1; then
        log_info "Running shellcheck"
        local script_file
        while IFS= read -r -d '' script_file; do
            if ! shellcheck -x "${script_file}"; then
                failed=1
            fi
        done < <(find "${repo_root_dir}/scripts" -type f -name '*.sh' -print0)
    else
        log_warn "shellcheck not found on PATH; skipping shell lint (install shellcheck to enable it)"
    fi

    if [[ "${failed}" -ne 0 ]]; then
        die "One or more lint checks failed." 1
    fi

    log_info "All lint checks passed"
}

main "$@"