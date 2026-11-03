#!/usr/bin/env bash
# deploy_app.sh — Copy the app (src/) onto the ESP32-S3 running MicroPython.
# Uses mpremote mount-free copy: wipes / then uploads src tree.
#
# Usage: ./scripts/deploy_app.sh [/dev/ttyACM0]
set -euo pipefail

PORT="${1:-/dev/ttyACM0}"
SRC="$(cd "$(dirname "$0")/../app" && pwd)"

echo "==> Deploying $SRC to $PORT"
mpremote connect "$PORT" fs cp -r "$SRC"/ : 2>&1 || {
    echo "fs cp -r failed; falling back to per-file upload"
    find "$SRC" -type f | while read -r f; do
        rel="${f#$SRC/}"
        echo "  -> $rel"
        mpremote connect "$PORT" fs mkdir -p ":$(dirname "$rel")" 2>/dev/null || true
        mpremote connect "$PORT" fs cp "$f" ":$rel"
    done
}
echo "==> Done. Reset the board (ctrl-d in REPL) to run main.py."
