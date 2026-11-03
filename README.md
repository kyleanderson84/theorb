# The Orb — Build Guide

ESP32-S3 multitool (Flipper-style) running full MicroPython + `micropython-touch`,
with an agentic runtime: a frozen supervisor + hot-swappable payload driven by a
remote AI backend. See `docs/AGENT_ARCHITECTURE.md`.

## Repository layout

```
app/                     VFS deploy set (copied to the board filesystem)
  main.py                entry point -> screens.BaseScreen
  screens.py             menu + live Agent status screen
  touch_setup.py         ILI9341 + FT6336 init -> Display
  agent_payload.py       hot-swappable payload (cloud agent overwrites this)
  config/
    supervisor.json      epoch_ms, sync_url, net_timeout
    known_nets.json      SSID -> password

micropython/ports/esp32/modules/   FROZEN into firmware:
  agent/                 supervisor, net, runner
  drivers/               ili93xx/ili9341.py (patched INVON), boolpalette
  gui/                   micropython-touch GUI (demos excluded)
  touch/                 ft6206 + friends
  cc1101.py es8311_init.py ft6x36.py   hardware drivers (baked in)

firmware/                built firmware image
scripts/                 build_firmware.sh, deploy_app.sh
tests/                   bringup_display.py
docs/                    HARDWARE_REFERENCE.md, AGENT_ARCHITECTURE.md
archive/                 previous LVGL/hacked attempt
```

## Build status
- MicroPython **v1.29.0**, ESP-IDF **v5.5.2** (recommended pairing) — confirmed.
- Board: **ESP32_GENERIC_S3 / SPIRAM_OCT** (8MB OPI PSRAM, 16MB QSPI flash).
- Built image: `firmware/theorb-mpy-v1.29-s3-oct16mb.bin` (~2.77MB).
- Partitions: 3MB app + **13.2MB VFS** filesystem.
- Frozen: agent core + GUI + drivers. VFS: app shell + payload + config.

## Flash
```bash
./scripts/build_firmware.sh        # rebuild (sources ESP-IDF, makes firmware)
# then flash the printed esptool command, e.g.:
esptool --chip esp32s3 -p /dev/ttyACM0 --before default_reset --after hard_reset \
  write_flash --flash_mode dio --flash_size 16MB 0x0 \
  micropython/ports/esp32/build-ESP32_GENERIC_S3-SPIRAM_OCT/bootloader/bootloader.bin \
  micropython/ports/esp32/build-ESP32_GENERIC_S3-SPIRAM_OCT/partition_table/partition-table.bin \
  firmware/theorb-mpy-v1.29-s3-oct16mb.bin
```

## Deploy the app (VFS)
```bash
./scripts/deploy_app.sh /dev/ttyACM0    # copies app/ -> board :/
```

## Bring-up order
1. Flash firmware from above.
2. **Verify panel** before touch: deploy app/, then `import bringup_display`
   (copy it to the board first) — expect red→green→blue.
   - Garbled? Try SCK=12 vs 14 (see docs/HARDWARE_REFERENCE.md).
   - Inverted colours? Driver sends INVON (0x21); flip via `ssd.invert(False)`.
3. **Calibrate touch**: `import touch.setup`, tap the crosses, paste the printed
   `tpad.init(...)` into `app/touch_setup.py`, redeploy.
4. Reset -> `main.py` shows the menu; open **Agent** for the live supervisor view.
5. Set `config/supervisor.json` `sync_url` to your backend to enable epochs.

## Hardware
ESP32-S3R8 · ILI9341V 240x320 (landscape 320x240, inversion ON) · FT6336G touch
(I2C 0x38, FT6206-family) · ES8311 codec · CC1101/NRF24 on shared SPI.
Full pin map: `docs/HARDWARE_REFERENCE.md`.

## Library notes
- `drivers/ili93xx/ili9341.py` patched: sends `INVON (0x21)` + `invert()` method.
- `usd=True` (unscaled) required unless scaled fonts frozen.
- GUI/touch/drivers are frozen; edit `micropython/ports/esp32/modules/` and rebuild
  to change them. Edit `app/` and redeploy for app/payload/config changes.
