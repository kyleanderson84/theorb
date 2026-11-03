# The Orb — ES3C28P Hardware Reference

Board: **ES3C28P** — 2.8" IPS ESP32-S3 display module
Source of truth: `docs/board_manuals/ES3C28P_pins_arduino.h` and `ES3C28P_interface.cpp`

## SoC / flash / RAM
- ESP32-S3R8 (QFN56, rev v0.2), dual-core + LP core, 240MHz
- **8MB embedded OPI PSRAM**
- **16MB QSPI flash**
- Wi-Fi + BT 5 (LE)

## Display — ILI9341V (SPI, dedicated bus)
| Signal | GPIO |
|--------|------|
| TFT_MOSI | 11 |
| TFT_MISO | 13 |
| TFT_SCK  | 12 |
| TFT_CS   | 10 |
| TFT_DC   | 46 |
| TFT_RST  | -1 (tied to CHIP_PU / board reset) |
| TFT_BL   | 45 (HIGH = on) |

- Resolution native: 240x320 (portrait). Used landscape 320x240.
- `TFT_INVERSION_ON` — inversion must be enabled to fix colors.
- CONFIRMED working pins (from Bruce's TFT_eSPI User_Setup + verified on-hardware
  color fill): SCK=12, MOSI=11, MISO=13, 40MHz. GPIO14 is the *expansion* SPI
  bus (radio), NOT the TFT. Using SCK=14 produces a blank screen.

## Touch — FT6336G (I2C)
| Signal | GPIO |
|--------|------|
| TOUCH_SDA | 16 |
| TOUCH_SCL | 15 |
| TOUCH_RST | 18 |
| TOUCH_INT | 17 |
| Address   | 0x38 |

- Register protocol same family as FT6236/FT6206/CST816 family.
  - Reg 0x02: number of touches
  - Reg 0x03+: touch point 1 X/Y
- micropython-touch `ft6206.py` driver targets this family at addr 0x38.
  Verify chip ID: reg 0xA8 == 0x11, reg 0xA3 in (0x06, 0x36, 0x64).

## I2C bus (shared)
- SDA = 16, SCL = 15
- Touch FT6336G @ 0x38, Audio ES8311 @ 0x18

## Audio — ES8311 codec + FM8002E amp
| Signal | GPIO |
|--------|------|
| I2S_MCLK | 4 |
| I2S_BCLK / SCLK | 5 |
| I2S DOUT (ESP32→ES8311 SDIN, playback) | 8 |
| I2S DIN (ES8311 SDOUT→ESP32, record) | 6 |
| AMP_EN (FM8002E, active LOW enable) | 1 |
- Amp: HIGH = disabled, LOW = enabled.

## Radio (via main SPI bus: MOSI=3, SCK=14, MISO=2, SS=21)
- CC1101: GDO0 = 2, SS = 21
- NRF24: CE = 3, SS = 21
- W5500 ethernet: SS = -1 (not wired)

## SD card — SDIO mode (not SPI)
- CLK = 38, CMD = 40, D0 = 39

## Misc
- Battery ADC: GPIO 9 (ADC1 ch8), x2 divider. 2500mV=0%, 4200mV=100%.
  Read via `battery.py` (uses read_uv() for calibrated mV).
- No charge-status pin on this board (Bruce's isCharging() returns false).
  Charging shown via voltage heuristic (>=4150mV) in battery.status_str().
- BOOT button: GPIO 0 (active LOW)
- USB: VID 0x303a PID 0x1001

## Pin conflicts to watch
- GPIO 2 = CC1101 GDO0 AND SPI MISO
- GPIO 3 = NRF24 CE AND SPI MOSI
- GPIO 21 = CC1101/NRF24 SS (shared)
- GPIO 14 alleged SCK but also possibly SPI bus shared with radio — verify.
