# bringup_display.py — Step 1 bring-up: verify the panel only, no touch.
# Run at the REPL:  import bringup_display
# Expect: solid red, then green, then blue fill, then a white "OK" label.
# If colours are inverted, toggle ssd.invert(False)/True below.

import gc
from machine import Pin, SPI
from drivers.ili93xx.ili9341 import ILI9341 as SSD

spi = SPI(1, baudrate=30_000_000, polarity=0, phase=0, sck=Pin(14), mosi=Pin(11))
pcs = Pin(10, Pin.OUT, value=1)
pdc = Pin(46, Pin.OUT, value=0)
prst = Pin(46, Pin.OUT, value=1)
Pin(45, Pin.OUT, value=1)  # backlight on

gc.collect()
ssd = SSD(spi, pcs, pdc, prst, height=240, width=320, usd=True)
print("Framebuffer allocated. free=", gc.mem_free())

from gui.core.tgui import Display, quiet
quiet()
display = Display(ssd)
ssd.fill(0xF800)  # red RGB565
import time
time.sleep(1)
ssd.fill(0x07E0)  # green
time.sleep(1)
ssd.fill(0x001F)  # blue
time.sleep(1)
ssd.fill(0x0000)
print("If you saw red/green/blue, display is OK.")
