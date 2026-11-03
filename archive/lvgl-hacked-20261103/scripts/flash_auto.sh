#!/usr/bin/env bash
set -u
PORT="${1:-/dev/ttyACM0}"
BUILD=/home/kyle_dude/theorb/micropython/ports/esp32/build-ESP32_GENERIC_S3-SPIRAM_OCT
LOG=/home/kyle_dude/theorb/flash_auto.log
export IDF_PATH=/home/kyle_dude/esp-idf
export PATH="$IDF_PATH/tools:$PATH"

: > "$LOG"
echo "watcher started $(date)" >> "$LOG"

attempt=0
while true; do
    attempt=$((attempt + 1))
    echo "--- attempt $attempt $(date +%H:%M:%S) ---" >> "$LOG"
    if timeout 12 esptool --chip esp32s3 -p "$PORT" --before default-reset --after no-reset --connect-attempts 1 chip-id >> "$LOG" 2>&1; then
        echo "REACHABLE — flashing custom ESP32-S3 firmware" >> "$LOG"
        timeout 60 esptool --chip esp32s3 -p "$PORT" --before default-reset --after no-reset erase_flash >> "$LOG" 2>&1
        ( cd "$BUILD" && timeout 180 esptool --chip esp32s3 -p "$PORT" --before default-reset --after hard-reset write_flash @flash_args ) >> "$LOG" 2>&1
        rc=$?
        if [ $rc -eq 0 ]; then
            echo "FLASH_DONE $(date)" >> "$LOG"
            exit 0
        else
            echo "FLASH_FAIL rc=$rc $(date)" >> "$LOG"
        fi
    fi
    sleep 2
done
