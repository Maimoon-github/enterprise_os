#!/bin/bash
set -e

DISPLAY_NUM=${DISPLAY_NUM:-1}
export DISPLAY=:${DISPLAY_NUM}
VNC_PORT=${VNC_PORT:-5901}

echo "Starting x11vnc on display :${DISPLAY_NUM} (port ${VNC_PORT})..."

(x11vnc -display "$DISPLAY" \
    -forever \
    -shared \
    -wait 50 \
    -rfbport "$VNC_PORT" \
    -nopw \
    -listen 0.0.0.0 \
    >/tmp/x11vnc.log 2>&1) &

x11vnc_pid=$!

timeout=15
while [ $timeout -gt 0 ]; do
    if netstat -tuln 2>/dev/null | grep -q ":${VNC_PORT} "; then
        break
    fi
    sleep 0.5
    ((timeout--))
done

echo "x11vnc started successfully on port ${VNC_PORT} (PID: $x11vnc_pid)."
