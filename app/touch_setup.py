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
# Authoritative pins from Bruce's working TFT_eSPI User_Setup (ES3C28P):
#   TFT_MOSI=11  TFT_SCLK=12  TFT_MISO=13  CS=10  DC=46  BL=45  RST=-1
#   SPI 40MHz, ILI9341, inversion ON.
# NOTE: SCK is 12 (not 14). GPIO14 is the *expansion* SPI bus, not the TFT.
_TFT_SCK = 12
_TFT_MOSI = 11
_TFT_CS = 10
_TFT_DC = 46
_TFT_BL = 45

spi = SPI(
    1,
    baudrate=40_000_000,
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
# Backlight (GPIO45) is owned by power.py via PWM (brightness control).
# Do not drive it as a plain output here.

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
    # Let the driver recover a wedged FT6336 by pulsing RST + restoring config.
    def _touch_reset():
        tpad.reset(_tp_rst)
    tpad._reset_cb = _touch_reset
except Exception as e:
    print("touch init failed (display-only):", e)
    tpad = None
    _touch_ok = False

if tpad is not None:
    # Orientation mapping (measured from raw corner taps on this unit).
    # Raw FT6336 coords are portrait 240x320 (x:0..240, y:0..320).
    # Screen is landscape 320x240.  Desired: col = raw_y, row = 240 - raw_x.
    # In precal mode poll() does: col=raw_x, row=raw_y, then rr/rc reflect,
    # then transpose swaps. To achieve the above: rr=False, rc=True, trans=True.
    #   xpix(=_xpix)=240, ypix(=_ypix)=320  (raw portrait dims)
    tpad.init(240, 320, 0, 0, 239, 319, True, False, True)

from gui.core.tgui import Display, quiet
quiet()
if tpad is not None:
    display = Display(ssd, tpad)
else:
    display = Display(ssd)

# ---- Power: apply saved backlight brightness, register display for power-off ----
try:
    import power
    power.init()
    power.register_display(ssd)
except Exception as e:
    print("power init failed:", e)
