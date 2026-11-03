# Replicate BRUCE's exact FT6336 init sequence
from machine import Pin, I2C
import time

TP_SDA, TP_SCL, TP_RST, TP_INT = 16, 15, 18, 17
TP_ADDR = 0x38

rst = Pin(TP_RST, Pin.OUT)
rst.value(0); time.sleep_ms(10)
rst.value(1); time.sleep_ms(300)

i2c = I2C(0, sda=Pin(TP_SDA), scl=Pin(TP_SCL), freq=400000)
scan = i2c.scan()
print("scan:", scan)

if TP_ADDR in scan:
    vid = i2c.readfrom_mem(TP_ADDR, 0x00, 1)[0]   # FT_ID_G_FTL_Version
    ver = i2c.readfrom_mem(TP_ADDR, 0xA8, 1)[0]   # library version
    print("device ID: 0x%02x (expect 0x11 = FT6336G)" % vid)
    print("version:   0x%02x" % ver)
else:
    print("touch controller NOT found on bus")
