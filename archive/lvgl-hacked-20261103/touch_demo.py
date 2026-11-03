import time
from ili9341 import Display
from ft6x36 import FT6336
from machine import I2C, Pin, soft_reset

dsp = Display(cs=10, dc=46, bl=45, width=240, height=320, rotation=0)
dsp.clear(0x0000)
dsp.text("Touch demo - Ctrl-C to exit", 8, 8, 0x07E0, 1)

i2c = I2C(0, scl=Pin(15), sda=Pin(16))
ft = FT6336(i2c)

try:
    while True:
        if ft.scan():
            x, y = ft.position()
            dsp.fill_rectangle(x, y, 3, 3, 0xFFFF)
            print("touch:", x, y)
        time.sleep_ms(20)
except KeyboardInterrupt:
    print("exiting touch demo")
    soft_reset()
