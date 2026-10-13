#!/bin/bash
set -e

DISPLAY_NUM=${DISPLAY_NUM:-1}
export DISPLAY=:${DISPLAY_NUM}
TINT2RC="${HOME}/internal_sandbox/config/tint2/tint2rc"

echo "Starting tint2 on display :${DISPLAY_NUM}..."
if [ -f "$TINT2RC" ]; then
    tint2 -c "$TINT2RC" >/tmp/tint2.log 2>&1 &
else
    tint2 >/tmp/tint2.log 2>&1 &
fi

echo "tint2 launched successfully."
