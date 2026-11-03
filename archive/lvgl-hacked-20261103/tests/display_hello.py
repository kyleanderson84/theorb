import time
from machine import Pin, SPI

from ili9341 import Display

spi = SPI(1, baudrate=40_000_000, polarity=0, phase=0, sck=Pin(12), mosi=Pin(11))
d = Display(cs=10, dc=46, bl=45, spi=spi, rotation=1)
d.clear(0x0000)
d.text("Hello World!", 20, 20, 0xFFFF, scale=2)
d.text("ESP32-S3 + ILI9341", 20, 60, 0x07E0, scale=2)
d.text("The Orb is alive.", 20, 100, 0xF81F, scale=2)
d.fill_rectangle(20, 150, 280, 40, 0x0007)
d.text("RGB565 frame active", 40, 170, 0xFFFF, scale=1)
print("display test done")
