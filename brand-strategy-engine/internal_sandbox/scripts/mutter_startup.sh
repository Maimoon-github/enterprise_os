#!/bin/bash
set -e

DISPLAY_NUM=${DISPLAY_NUM:-1}
export DISPLAY=:${DISPLAY_NUM}

echo "Starting mutter window manager on display :${DISPLAY_NUM}..."
XDG_SESSION_TYPE=x11 mutter --replace --sm-disable >/tmp/mutter.log 2>&1 &

timeout=15
while [ $timeout -gt 0 ]; do
    if xdotool search --class "mutter" >/dev/null 2>&1; then
        break
    fi
    sleep 0.5
    ((timeout--))
done

echo "mutter window manager is active."
