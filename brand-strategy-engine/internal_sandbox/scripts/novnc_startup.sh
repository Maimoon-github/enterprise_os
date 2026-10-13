#!/bin/bash
set -e

VNC_PORT=${VNC_PORT:-5901}
NOVNC_PORT=${NOVNC_PORT:-6080}

echo "Starting noVNC proxy bridging localhost:${VNC_PORT} to port ${NOVNC_PORT}..."

if [ -f "/opt/noVNC/utils/novnc_proxy" ]; then
    /opt/noVNC/utils/novnc_proxy \
        --vnc "localhost:${VNC_PORT}" \
        --listen "$NOVNC_PORT" \
        --web /opt/noVNC \
        >/tmp/novnc.log 2>&1 &
    echo "noVNC started on port ${NOVNC_PORT}."
else
    echo "noVNC not found in /opt/noVNC, skipping."
fi
