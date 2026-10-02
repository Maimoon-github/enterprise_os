#!/usr/bin/env bash
# ==============================================================================
# Enterprise OS - Hardened Sandbox Provisioner Production Deployment Script
# Configures dedicated OS users, groups, systemd units, socket permissions, and pins Bubblewrap.
# ==============================================================================

set -euo pipefail

echo "==> Configuring Enterprise OS Production Security Boundary..."

# 1. Ensure dedicated system user identities exist
if ! getent group enterprise-os-sandbox >/dev/null 2>&1; then
    echo "Creating group: enterprise-os-sandbox"
    groupadd --system enterprise-os-sandbox
fi

if ! getent passwd enterprise-os-sandbox >/dev/null 2>&1; then
    echo "Creating user: enterprise-os-sandbox (Dedicated unprivileged execution boundary)"
    useradd --system --gid enterprise-os-sandbox --shell /usr/sbin/nologin \
        --comment "Enterprise OS Hardened Sandbox Provisioner" enterprise-os-sandbox
fi

if ! getent group enterprise-os-backend >/dev/null 2>&1; then
    echo "Creating group: enterprise-os-backend"
    groupadd --system enterprise-os-backend
fi

if ! getent passwd enterprise-os-backend >/dev/null 2>&1; then
    echo "Creating user: enterprise-os-backend (API & Intelligence Engine execution identity)"
    useradd --system --gid enterprise-os-backend --shell /usr/sbin/nologin \
        --comment "Enterprise OS Backend API Service" enterprise-os-backend
fi

# Add backend user to sandbox group for socket accessibility
usermod -a -G enterprise-os-sandbox enterprise-os-backend

# Ensure sandbox user can read workspace files under host user group
HOST_USER=$(id -un 1000 2>/dev/null || echo "maimoon-amin")
if getent group "$HOST_USER" >/dev/null 2>&1; then
    usermod -a -G "$HOST_USER" enterprise-os-sandbox
    echo "Added enterprise-os-sandbox to supplementary group: $HOST_USER"
fi

# Ensure space-free symlink for systemd path safety
if [ ! -L "/home/$HOST_USER/enterprise_os" ]; then
    ln -s "/home/$HOST_USER/Antigravity code/enterprise_os" "/home/$HOST_USER/enterprise_os"
    echo "Created workspace symlink: /home/$HOST_USER/enterprise_os"
fi

# 2. Configure runtime socket directory (/run/enterprise_os)
RUNTIME_DIR="/run/enterprise_os"
mkdir -p "$RUNTIME_DIR"
chown enterprise-os-backend:enterprise-os-sandbox "$RUNTIME_DIR"
chmod 0770 "$RUNTIME_DIR"
echo "Configured runtime directory: $RUNTIME_DIR (0770)"

# 3. Verify Bubblewrap installation (Requires >= 0.12.0, target 0.13.0)
BWRAP_BIN=$(which bwrap || true)
if [ -z "$BWRAP_BIN" ]; then
    echo "ERROR: Bubblewrap binary not found. Install bubblewrap >= 0.12.0."
    exit 1
fi

BWRAP_VER=$("$BWRAP_BIN" --version | awk '{print $2}')
echo "Installed Bubblewrap version: $BWRAP_VER"

# 4. Copy systemd unit definitions
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp "$SCRIPT_DIR/enterprise-os-provisioner.socket" /etc/systemd/system/
cp "$SCRIPT_DIR/enterprise-os-provisioner.service" /etc/systemd/system/

systemctl daemon-reload
systemctl enable --now enterprise-os-provisioner.socket

echo "==> Enterprise OS Sandbox Provisioner Socket Activated Successfully."
systemctl status enterprise-os-provisioner.socket --no-pager
