#!/usr/bin/env bash
set -euo pipefail

echo "[sandbox-lifecycle] Initiating deterministic session scrubbing..."

# 1. Target specific sandbox workspace/attempt if supplied
if [ -n "${SANDBOX_WORKSPACE:-}" ] && [ -d "${SANDBOX_WORKSPACE}" ]; then
    echo "[sandbox-lifecycle] Scrubbing specific attempt workspace: ${SANDBOX_WORKSPACE}..."
    rm -rf "${SANDBOX_WORKSPACE:?}"/* 2>/dev/null || true
fi

# 2. Terminate owned attempt process tree if PID is supplied
if [ -n "${SANDBOX_ATTEMPT_PID:-}" ]; then
    echo "[sandbox-lifecycle] Terminating owned attempt process group ${SANDBOX_ATTEMPT_PID}..."
    kill -TERM -"${SANDBOX_ATTEMPT_PID}" 2>/dev/null || kill -KILL -"${SANDBOX_ATTEMPT_PID}" 2>/dev/null || true
fi

# 3. Scrub attempt-scoped credentials or tokens
unset SANDBOX_API_KEY JWT_PUBLIC_KEY SBX_TOKEN || true
if [ -n "${SANDBOX_WORKSPACE:-}" ]; then
    rm -f "${SANDBOX_WORKSPACE}"/.sbx_token* 2>/dev/null || true
fi

echo "[sandbox-lifecycle] Attempt scrubbing complete."
