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

## Radio — CC1101 (external module, SPI) — CONFIRMED WORKING
- Driver: `frozen/modules/cc1101.py` (`CC1101`, `open_radio()`). Decode +
  capture storage: `frozen/modules/subghz.py`. UI:
  `frozen/modules/subghz_screens.py` (scanner, OOK capture, capture browser).
  Verified `PARTNUM=0x00`, `VERSION=0x14`, live RSSI, and end-to-end OOK capture
  of a 315 MHz car-remote.
- Actual wiring (differs from the Bruce/board manual defaults!):
  | Signal | GPIO |
  |--------|------|
  | SCK | 2 |
  | MOSI (SI) | 14 |
  | MISO (SO) / GDO1 | 3 |
  | CSN | 21 |
  | GDO0 | 15 |
  | GDO2 | 16 |
  | VCC / GND | 3V3 / GND |
- SPI mode 0. Use **1 MHz**: the raw-OOK RX FIFO fills at ~100 kBaud (12.5 kB/s)
  and *must* be drained faster than it fills or it overflows (marcstate 0x11)
  and the radio stalls. 100 kHz / 400 kHz cannot keep up; 1 MHz sustains
  ~12.4 kB/s (verified). The board-manual mapping (SCK=14/MOSI=3/MISO=2) is
  WRONG for this module.
- GDO0 (15) and GDO2 (16) sit on the shared touch/audio I2C bus (SCL=15,
  SDA=16), so `IOCFG0/1/2` are set to `0x2E` (tri-state) to avoid contention.
  RX uses the FIFO, not GDO — carrier-sense GDO would conflict with I2C.
- SPI access quirks found on this hardware: config registers (0x00–0x2F) read
  with a normal single access; **status registers (0x30–0x3D) must be read with
  the burst bit set (0x40) or they return garbage**; and a *single* access to a
  status register forces the radio back to IDLE. `SIDLE` before `SRX` is needed
  to (re)enter RX. All handled inside the driver.
- Board-default `rfModule = CC1101_SPI_MODULE` in the Bruce interface.
- Raw OOK RX: `config_ook()` sets `MDMCFG2 = 0x30` (OOK — note `0x02` is 2-FSK,
  a trap) and `PKTCTRL0 = 0x02` (NORMAL format, LENGTH_CONFIG_INFINITE) so the
  demodulated bitstream streams into the RX FIFO. `capture()` gates reads on
  RSSI (the slicer idles at `0xFF`); `read_rx_fifo(n)` drains the FIFO.
  `PKTCTRL0` layout: bits5:4 = PKT_FORMAT (0x30), bit2 = CRC_EN (0x04),
  bits1:0 = LENGTH_CONFIG (0x03; 02 = infinite).
- `symbol_us()` derives the symbol period from `MDMCFG4/3` (the stock `_OOK`
  profile is ~100 kBaud ⇒ ~10 µs/bit), giving fine temporal resolution. One FIFO
  bit = one slicer sample.
- Decoding (`subghz.py`): RLE the bitstream → pulse widths, then a best-effort
  EV1527/PT2262 tri-bit decode (sync = short high + long low, then 1u/3u pairs);
  both slicer polarities are tried. Captures persist under `/captures/*.cap`
  (JSON header + raw bytes) → browse/decode/delete on the Sub-GHz screen.
- No RF transmit: OOK TX would need GDO0, which shares I2C SCL (GPIO15), so GDO
  pins stay tri-stated — RX is FIFO-only and replay is view/decode, not TX.

## Other radio
- NRF24: CE = 3, SS = 21 (shares the SPI bus; not yet wired/tested).
- W5500 ethernet: SS = -1 (not wired).

## SD card — SDIO mode (not SPI)
- CLK = 38, CMD = 40, D0 = 39

## NFC — PN532 (external module, UART / HSU)
- No on-board NFC. A PN532 breakout is wired to **UART0** (confirmed working,
  chip reports `IC 0x32 firmware v1.6`):
  - ESP TX (GPIO43 / U0TXD) -> PN532 RXD
  - ESP RX (GPIO44 / U0RXD) <- PN532 TXD
  - GND common, VCC 5V (VIN) or 3V3; DIP switches set to **HSU** (both OFF), 115200 8N1.
- UART0 is free here because the REPL/console runs on the native USB-Serial-JTAG
  peripheral (`CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG=y`), not UART0.
- Driver: `frozen/modules/pn532.py` (`PN532`). UI: `app/nfc_screens.py`.
- HSU quirks the driver handles: the PN532 ACK is the special 6-byte
  `00 00 FF 00 FF 00` (its LEN=0/LCS=FF breaks the usual LEN+LCS=0 rule); a cold
  chip can drop the first frame (retry with the wakeup `55 55 00...`); and
  `InListPassiveTarget` can take a few hundred ms to answer, so poll for it.
- Board-default `rfidModule = PN532_I2C_MODULE` in the Bruce interface is NOT
  what we use; our wiring is UART/HSU (there is no NFC device at I2C 0x24).
- Tag note: EMV/debit cards (SAK 0x20, ISO14443-4) couple weakly with small
  coils and read only intermittently; plain NTAG / MIFARE tags read reliably.

## Misc
- Battery ADC: GPIO 9 (ADC1 ch8), x2 divider. 2500mV=0%, 4200mV=100%.
  Read via `battery.py` (uses read_uv() for calibrated mV).
- No charge-status pin on this board (Bruce's isCharging() returns false).
  Charging shown via voltage heuristic (>=4150mV) in battery.status_str().
- BOOT button: GPIO 0 (active LOW)
- USB: VID 0x303a PID 0x1001

## Pin conflicts to watch
- GPIO 15 = touch/audio I2C SCL AND CC1101 GDO0 (GDO kept tri-stated)
- GPIO 16 = touch/audio I2C SDA AND CC1101 GDO2 (GDO kept tri-stated)
- GPIO 3 = CC1101 MISO/SPI MISO AND NRF24 CE
- GPIO 21 = CC1101/NRF24 SS (shared)
- GPIO 2 = CC1101 SCK (the board manual's "GDO0/SCK=14" is a mislabel for this
  module — see the Radio section above).
