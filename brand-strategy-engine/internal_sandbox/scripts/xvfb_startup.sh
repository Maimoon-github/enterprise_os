#!/bin/bash
set -e

DPI=96
DISPLAY_NUM=${DISPLAY_NUM:-1}
WIDTH=${WIDTH:-1920}
HEIGHT=${HEIGHT:-1080}
RES_AND_DEPTH="${WIDTH}x${HEIGHT}x24"

check_xvfb_running() {
    if [ -e "/tmp/.X${DISPLAY_NUM}-lock" ]; then
        return 0
    else
        return 1
    fi
}

wait_for_xvfb() {
    local timeout=15
    local start_time=$(date +%s)
    while ! xdpyinfo -display ":${DISPLAY_NUM}" >/dev/null 2>&1; do
        if [ $(($(date +%s) - start_time)) -gt $timeout ]; then
            echo "Xvfb failed to start within $timeout seconds on :${DISPLAY_NUM}" >&2
            return 1
        fi
        sleep 0.1
    done
    return 0
}

if check_xvfb_running; then
    echo "Xvfb is already running on display :${DISPLAY_NUM}"
    exit 0
fi

echo "Starting Xvfb on display :${DISPLAY_NUM} with resolution ${RES_AND_DEPTH}..."
Xvfb ":${DISPLAY_NUM}" -ac -screen 0 "$RES_AND_DEPTH" -retro -dpi $DPI -nolisten tcp &
XVFB_PID=$!

if wait_for_xvfb; then
    echo "Xvfb started successfully on display :${DISPLAY_NUM} (PID: $XVFB_PID)"
else
    echo "Xvfb failed to start" >&2
    kill $XVFB_PID 2>/dev/null || true
    exit 1
fi
