#!/usr/bin/env bash
# ==============================================================================
# Enterprise OS Clean-Room Release Gate & Certification Pipeline
# NIST SSDF (SP 800-218) & SLSA v1.2 Compliant
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "================================================================================"
echo "Starting Enterprise OS Clean-Room Release Gate"
echo "Root: ${ROOT_DIR}"
echo "================================================================================"

cd "${ROOT_DIR}"

# Run through enterprise_os conda environment
conda run -n enterprise_os python release/pipeline.py "$@"

echo "================================================================================"
echo "Enterprise OS Release Pipeline Successfully Completed and Certified!"
echo "================================================================================"
