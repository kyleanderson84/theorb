# touch_setup.py — ES3C28P board setup for micropython-touch
# Hardware: ESP32-S3R8, ILI9341V 240x320 TFT, FT6336G touch, 8MB PSRAM
# See docs/HARDWARE_REFERENCE.md for the authoritative pin map.
#
# This is imported once at startup (by main.py) to create the display and
# touch objects. Keep it minimal and instantiate the framebuffer early so the
# 38KB GS4 buffer is allocated before other modules fragment the heap.

import gc
from machine import Pin, I2C, SPI
from drivers.ili93xx.ili9341 import ILI9341 as SSD

# ---- Display SPI bus ----
# Board reference: TFT_MOSI=11, TFT_SCK=14 (verify on scope), CS=10, DC=46,
# BL=45, RST=-1 (tied to CHIP_PU). MISO not needed for write-only panel.
_TFT_SCK = 14
_TFT_MOSI = 11
_TFT_CS = 10
_TFT_DC = 46
_TFT_BL = 45

spi = SPI(
    1,
    baudrate=30_000_000,
    polarity=0,
    phase=0,
    sck=Pin(_TFT_SCK),
    mosi=Pin(_TFT_MOSI),
)

pcs = Pin(_TFT_CS, Pin.OUT, value=1)
pdc = Pin(_TFT_DC, Pin.OUT, value=0)
# RST is tied to board reset; use a dummy output pin held high so the driver
# still has an object to poke.
prst = Pin(_TFT_DC, Pin.OUT, value=1)

# Backlight: HIGH = on
bl = Pin(_TFT_BL, Pin.OUT, value=1)

gc.collect()
# 240x320 panel; usd=True (unscaled) — required when no scaled fonts are frozen.
# Invert colours to match the Panelly/TFT_INVERSION_ON requirement.
ssd = SSD(spi, pcs, pdc, prst, height=240, width=320, usd=True)
# NOTE: if colours look inverted at runtime, call ssd.invert(True) via the
# driver-specific hook; adjust here once verified on hardware.

# ---- Touch (FT6336G, I2C @ 0x38) ----
# IMPORTANT: this board's I2C only responds reliably at 400kHz; 100kHz yields
# ENODEV. Pulse TOUCH_RST (GPIO18) first so the chip is in a known state.
import time
from touch.ft6206 import FT6206

_tp_rst = Pin(18, Pin.OUT)
_tp_rst(0)
time.sleep_ms(20)
_tp_rst(1)
time.sleep_ms(150)

i2c = I2C(0, scl=Pin(15), sda=Pin(16), freq=400_000)
try:
    tpad = FT6206(i2c, ssd)
    _touch_ok = True
except Exception as e:
    print("touch init failed (display-only):", e)
    tpad = None
    _touch_ok = False

if tpad is not None:
    # Orientation: display used landscape (320x240). FT6206 raw coords are in
    # portrait (240x320); transpose + reflect to match. Verify with touch.setup
    # calibration, then lock values here.
    # (xpix, ypix, xmin, ymin, xmax, ymax, trans, rr, rc)
    tpad.init(ssd.height, ssd.width, 0, 0, 239, 319, True, True, False)

from gui.core.tgui import Display, quiet
quiet()
if tpad is not None:
    display = Display(ssd, tpad)
else:
    display = Display(ssd)
