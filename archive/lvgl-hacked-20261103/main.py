import time
from ili9341 import Display
from ft6x36 import FT6336
from machine import I2C, Pin

try:
    dsp = Display(cs=10, dc=46, bl=45, width=240, height=320, rotation=0)
    dsp.clear(0x0000)
    dsp.text("Hello World", 16, 150, 0xFFFF, 2)
    dsp.text("ES3C28P boot OK", 16, 200, 0x07E0, 1)
    i2c = I2C(0, scl=Pin(15), sda=Pin(16))
    ft = FT6336(i2c)
    print("main.py: display drawn, touch found, I2C:", i2c.scan())
except Exception as e:
    print("main.py error:", e)
