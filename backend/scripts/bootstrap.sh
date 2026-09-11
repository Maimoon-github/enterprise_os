#!/usr/bin/env bash
#
# scripts/bootstrap.sh — create (or reuse) the project virtual environment
# and install the backend package with its development dependencies.
# Idempotent: safe to re-run at any time, e.g. after pulling new deps.
#
# Usage: scripts/bootstrap.sh

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd -P)"
readonly SCRIPT_DIR
# shellcheck source=SCRIPTDIR/lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"

main() {
    require_cmd python3 "install Python 3.11 or newer"

    local repo_root_dir venv_path
    repo_root_dir="$(repo_root)"
    venv_path="$(venv_dir)"

    if [[ ! -d "${venv_path}" ]]; then
        log_info "Creating virtual environment at ${venv_path}"
        python3 -m venv "${venv_path}"
    else
        log_info "Reusing existing virtual environment at ${venv_path}"
    fi

    # shellcheck source=/dev/null
    source "${venv_path}/bin/activate"

    log_info "Upgrading pip"
    python -m pip install --quiet --upgrade pip

    log_info "Installing backend package with development dependencies"
    python -m pip install --quiet --editable "${repo_root_dir}[dev]"

    if [[ ! -f "${repo_root_dir}/.env" ]]; then
        log_info "Creating .env from .env.example"
        cp -- "${repo_root_dir}/.env.example" "${repo_root_dir}/.env"
    else
        log_info ".env already exists; leaving it untouched"
    fi

    log_info "Bootstrap complete. Activate with: source ${venv_path}/bin/activate"
}

main "$@"