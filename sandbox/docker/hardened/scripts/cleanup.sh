#!/usr/bin/env bash
set -euo pipefail

echo "[sandbox-lifecycle] Initiating deterministic session scrubbing..."

# 1. Terminate all browser, X11, and worker child processes
pkill -9 -f "chrome" || true
pkill -9 -f "chromium" || true
pkill -9 -f "Xvfb" || true
pkill -9 -f "x11vnc" || true
pkill -9 -f "python" || true
pkill -9 -f "node" || true

# 2. Scrub volatile directories
echo "[sandbox-lifecycle] Cleaning volatile directories..."
rm -rf /tmp/* /tmp/.* 2>/dev/null || true
rm -rf /run/* /run/.* 2>/dev/null || true
rm -rf /home/gem/Downloads/* 2>/dev/null || true
rm -rf /home/gem/.cache/* 2>/dev/null || true
rm -rf /home/gem/.config/google-chrome/* 2>/dev/null || true
rm -rf /home/gem/.config/chromium/* 2>/dev/null || true

# 3. Wipe ephemeral task workspace and attempt-specific scratch directories
if [ -n "${SANDBOX_WORKSPACE:-}" ] && [ -d "${SANDBOX_WORKSPACE}" ]; then
    echo "[sandbox-lifecycle] Scrubbing specific sandbox workspace: ${SANDBOX_WORKSPACE}..."
    rm -rf "${SANDBOX_WORKSPACE:?}"/* 2>/dev/null || true
fi

if [ -d "/workspace/ephemeral" ]; then
    echo "[sandbox-lifecycle] Scrubbing ephemeral task workspace..."
    rm -rf /workspace/ephemeral/* 2>/dev/null || true
fi

# 4. Scrub any task-scoped short-lived credentials or tokens in environment/files
unset SANDBOX_API_KEY JWT_PUBLIC_KEY SBX_TOKEN || true
rm -f /home/gem/.sbx_token* /tmp/.sbx_token* 2>/dev/null || true

echo "[sandbox-lifecycle] Scrubbing complete. Sandbox state wiped."
