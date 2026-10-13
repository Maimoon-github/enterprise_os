#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export DISPLAY=:${DISPLAY_NUM:-1}
export WIDTH=${WIDTH:-1920}
export HEIGHT=${HEIGHT:-1080}
export VNC_PORT=${VNC_PORT:-5901}
export NOVNC_PORT=${NOVNC_PORT:-6080}

echo "=== Initializing Internal Sandboxed VNC Display Subsystem ==="
"$SCRIPT_DIR/scripts/start_all.sh"
"$SCRIPT_DIR/scripts/novnc_startup.sh"

echo "=== Internal VNC Sandbox is running on DISPLAY ${DISPLAY} (RFB Port ${VNC_PORT}) ==="

# Trap termination signals and keep container alive
trap "echo 'Terminating VNC sandbox...'; exit 0" SIGINT SIGTERM
tail -f /dev/null
