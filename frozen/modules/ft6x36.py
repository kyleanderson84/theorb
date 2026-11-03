# FT6336 capacitive touch driver for LCDWiki ES3C28P (landscape 320x240).
import time, machine

class FT6336:
    def __init__(self, i2c, rst_pin=18):
        self.i2c = i2c
        self.addr = 0x38
        self.rst = machine.Pin(rst_pin, machine.Pin.OUT)
        self._init()

    def _init(self):
        self.rst.value(0); time.sleep_ms(10)
        self.rst.value(1); time.sleep_ms(100)
        for _ in range(5):
            try:
                self.i2c.writeto_mem(self.addr, 0x00, b'\x00')  # normal mode
                self.i2c.writeto_mem(self.addr, 0x12, b'\x00')  # disable auto sleep
                return
            except Exception:
                time.sleep_ms(20)
        print("touch init failed after retries")

    def scan(self):
        """Return number of active touches, recovering from ENODEV."""
        for _ in range(3):
            try:
                return self.i2c.readfrom_mem(self.addr, 0x02, 1)[0]
            except Exception:
                self._init()
        return 0

    def position(self):
        """Return (x, y) of the first touch in landscape (320x240) coords."""
        c = self.scan()
        if c == 0:
            return (0, 0)
        d = self.i2c.readfrom_mem(self.addr, 0x03, 6)
        x = ((d[0] & 0x0F) << 8) | d[1]
        y = ((d[2] & 0x0F) << 8) | d[3]
        # portrait(240x320) -> landscape(320x240), rotation 1
        lx = y
        ly = 240 - x
        lx = min(max(lx, 0), 319)
        ly = min(max(ly, 0), 239)
        return (lx, ly)