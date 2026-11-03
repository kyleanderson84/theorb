#!/usr/bin/env bash
# build_firmware.sh — Build stock MicroPython v1.29 for ES3C28P
#   ESP32-S3 / 8MB Octal PSRAM / 16MB QSPI flash
#
# Output: micropython/ports/esp32/build-ESP32_GENERIC_S3-SPIRAM_OCT/firmware.bin
#
# Prereqs (already present on this machine):
#   - ~/esp-idf @ v5.5.2
#   - ~/.espressif toolchain
#   - mpy-cross built
set -euo pipefail

MPY_DIR="${MPY_DIR:-/home/kyle_dude/theorb/micropython}"
IDF_PATH="${IDF_PATH:-$HOME/esp-idf}"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BOARD=THEORB_S3
VARIANT=

echo "==> Sourcing ESP-IDF ($IDF_PATH)"
# shellcheck disable=SC1091
source "$IDF_PATH/export.sh" >/dev/null

# --- Sync our tracked frozen sources into the MicroPython tree ---
# frozen/ is the git-tracked source of truth; micropython/ is build scratch.
if [ -d "$REPO_DIR/frozen" ]; then
    echo "==> Syncing frozen/ -> micropython/ports/esp32/"
    rm -rf "$MPY_DIR/ports/esp32/boards/THEORB_S3"
    cp -r "$REPO_DIR/frozen/board/THEORB_S3" "$MPY_DIR/ports/esp32/boards/"
    # Replace the frozen-modules payload with our tracked copy.
    rm -rf "$MPY_DIR/ports/esp32/modules/agent" \
           "$MPY_DIR/ports/esp32/modules/gui" \
           "$MPY_DIR/ports/esp32/modules/drivers" \
           "$MPY_DIR/ports/esp32/modules/touch"
    cp -r "$REPO_DIR/frozen/modules/." "$MPY_DIR/ports/esp32/modules/"
fi

cd "$MPY_DIR"

if [ ! -x mpy-cross/build/mpy-cross ]; then
    echo "==> Building mpy-cross"
    make -C mpy-cross
fi

cd ports/esp32

echo "==> Building $BOARD variant $VARIANT (8MB OCT PSRAM, 16MB flash)"
make BOARD="$BOARD" -j"$(nproc)"

BUILD_DIR="build-${BOARD}"
echo "==> Done. Firmware:"
ls -la "$MPY_DIR/ports/esp32/$BUILD_DIR/firmware.bin"
echo
echo "Flash with:"
echo "  esptool --chip esp32s3 -p /dev/ttyACM0 --before default_reset --after hard_reset \\"
echo "    write_flash --flash_mode dio --flash_size 16MB 0x0 \\"
echo "    $MPY_DIR/ports/esp32/$BUILD_DIR/bootloader/bootloader.bin \\"
echo "    $MPY_DIR/ports/esp32/$BUILD_DIR/partition_table/partition-table.bin \\"
echo "    $MPY_DIR/ports/esp32/$BUILD_DIR/firmware.bin"
