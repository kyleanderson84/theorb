#!/usr/bin/env bash
# flash.sh — robust flash for ESP32-S3 native USB-Serial-JTAG.
#
# The S3's USB-Serial-JTAG CDC endpoint can stall on writes if the running
# firmware or a prior failed flash wedged it. Strategy:
#   1. Try normal stub flash at 460800.
#   2. Fall back to no-stub at 115200.
#   3. Fall back to usb-reset + no-stub at 9600.
# If all fail the board needs a physical reset (unplug/replug or BOOT+RESET).
set -uo pipefail

PORT="${1:-/dev/ttyACM0}"
BUILD="${BUILD:-/home/kyle_dude/theorb/micropython/ports/esp32/build-THEORB_S3}"
FW="${FW:-/home/kyle_dude/theorb/firmware/theorb-mpy-v1.29-s3-oct16mb.bin}"

cd "$BUILD"

attempt() {
    local desc="$1"; shift
    echo "==> Attempt: $desc"
    if "$@"; then
        echo "==> SUCCESS ($desc)"
        return 0
    fi
    echo "==> failed ($desc)"
    sleep 2
    return 1
}

flash_stub() {
    esptool --chip esp32s3 -p "$PORT" -b 460800 \
        --before default-reset --after hard-reset \
        write-flash --flash-mode dio --flash-freq 80m --flash-size 16MB \
        0x0 bootloader/bootloader.bin \
        0x8000 partition_table/partition-table.bin \
        0x10000 "$FW"
}
flash_nostub() {
    esptool --chip esp32s3 -p "$PORT" -b 115200 --no-stub \
        --before default-reset --after hard-reset \
        write-flash --flash-mode dio --flash-freq 80m --flash-size 16MB \
        0x0 bootloader/bootloader.bin \
        0x8000 partition_table/partition-table.bin \
        0x10000 "$FW"
}
flash_usbreset() {
    esptool --chip esp32s3 -p "$PORT" -b 9600 --no-stub \
        --before usb-reset --after hard-reset \
        write-flash --flash-mode dio --flash-freq 80m --flash-size 16MB \
        0x0 bootloader/bootloader.bin \
        0x8000 partition_table/partition-table.bin \
        0x10000 "$FW"
}

attempt "stub 460800" flash_stub || \
attempt "no-stub 115200" flash_nostub || \
attempt "usb-reset no-stub 9600" flash_usbreset || {
    echo
    echo "ALL ATTEMPTS FAILED."
    echo "Physical reset required: UNPLUG the USB cable and plug it back in,"
    echo "or hold BOOT then tap RESET to enter download mode, then re-run this script."
    exit 1
}
