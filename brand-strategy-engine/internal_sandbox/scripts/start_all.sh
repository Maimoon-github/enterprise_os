#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Starting sandbox desktop display components..."
"$SCRIPT_DIR/xvfb_startup.sh"
"$SCRIPT_DIR/tint2_startup.sh"
"$SCRIPT_DIR/mutter_startup.sh"
"$SCRIPT_DIR/x11vnc_startup.sh"

echo "All internal sandbox desktop components successfully launched."
