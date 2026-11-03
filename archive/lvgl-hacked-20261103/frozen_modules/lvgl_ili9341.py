# Pure-Python ILI9341 driver for MicroPython LVGL binding
# No CFFI / espidf module required - uses machine.SPI + lv.C_Pointer
#
# Pins (theorb / LCDWiki ES3C28P):
#   SCK = 14, MOSI = 3, CS = 10, DC = 46, BL = 45
#   RST tied to CHIP_PU -> software reset only
#
# Display: 320x240 landscape, MADCTL 0x28 (rot+swap), inversion ON

import lvgl as lv
from machine import SPI, Pin


class ili9341:
    def __init__(
        self,
        sck=14,
        mosi=3,
        cs=10,
        dc=46,
        bl=45,
        spi_bus=2,
        width=320,
        height=240,
        invert=True,
        mhz=40,
        bl_active=1,
        double_buffer=True,
    ):
        self.width = width
        self.height = height
        self.cs = Pin(cs, Pin.OUT, value=1)
        self.dc = Pin(dc, Pin.OUT, value=0)
        self.bl = Pin(bl, Pin.OUT, value=0)
        self.spi = SPI(
            spi_bus,
            baudrate=mhz * 1000 * 1000,
            polarity=0,
            phase=0,
            firstbit=SPI.MSB,
            sck=Pin(sck),
            mosi=Pin(mosi),
            miso=None,
        )
        self._buf_size = width * height * 2

        # ---- init sequence ----
        self._sw_reset()
        self._cmd(0x01, b"\x00")
        self._delay(150)
        self._cmd(0x11, b"\x00")
        self._delay(120)
        self._cmd(0x3A, b"\x55")  # RGB565
        self._cmd(0x36, b"\x28")  # MADCTL: landscape, BGR swap
        self._cmd(0xC0, b"\x23\xB2")
        self._cmd(0xC1, b"\xC0")
        self._cmd(0xC5, b"\x3C\xC2\x00")
        self._cmd(0xC7, b"\x94")
        self._cmd(0x20, b"\x00")  # invert off
        if invert:
            self._cmd(0x21, b"\x00")  # invert on
        self._cmd(0xE0, bytes.fromhex("000012141A"))
        self._cmd(0xE1, bytes.fromhex("000012141A"))
        self._cmd(0xE2, bytes.fromhex("000012141A"))
        self._cmd(0xE3, bytes.fromhex("000012141A"))
        self._cmd(0xE4, bytes.fromhex("000012141A"))
        self._cmd(0xE5, bytes.fromhex("000012141A"))
        self._cmd(0x2A, bytes.fromhex("0000 01 3F".replace(" ", "")))
        self._cmd(0x2B, bytes.fromhex("0000 00 EF".replace(" ", "")))
        self._cmd(0x29, b"\x00")  # display on
        self._delay(100)

        self.bl.value(bl_active)

        # ---- LVGL display ----
        self.disp = lv.display_create(width, height)
        self.disp.set_flush_cb(self.flush)
        self.disp.set_color_format(lv.COLOR_FORMAT.RGB565)

        buf1 = bytearray(self._buf_size)
        buf2 = bytearray(self._buf_size) if double_buffer else None
        self.disp.set_buffers(
            buf1, buf2, len(buf1), lv.DISPLAY_RENDER_MODE.PARTIAL
        )

    # ---- low-level SPI commands ----
    def _sw_reset(self):
        self.cs.value(0)
        self.dc.value(0)
        self.spi.write(b"\x01")
        self.cs.value(1)

    def _cmd(self, c, data):
        self.cs.value(0)
        self.dc.value(0)
        self.spi.write(bytes([c]))
        self.cs.value(1)
        if data:
            self.cs.value(0)
            self.dc.value(1)
            self.spi.write(data)
            self.cs.value(1)

    def _delay(self, ms):
        import time

        time.sleep_ms(ms)

    def _set_window(self, x1, y1, x2, y2):
        self._cmd(0x2A, bytes([(x1 >> 8) & 0xFF, x1 & 0xFF, (x2 >> 8) & 0xFF, x2 & 0xFF]))
        self._cmd(0x2B, bytes([(y1 >> 8) & 0xFF, y1 & 0xFF, (y2 >> 8) & 0xFF, y2 & 0xFF]))

    # ---- LVGL flush callback ----
    def flush(self, disp, area, color_p):
        x1 = area.x1
        y1 = area.y1
        x2 = area.x2
        y2 = area.y2
        w = x2 - x1 + 1
        h = y2 - y1 + 1

        self._set_window(x1, y1, x2, y2)

        # Copy pixel data from the C pointer into a bytearray
        n = w * h * 2
        p = lv.C_Pointer()
        p = color_p
        buf = bytearray(n)
        for i in range(n):
            buf[i] = color_p[i]

        self._cmd(0x2C, bytes(buf))
        self.cs.value(1)
        self.disp.flush_ready()

    # ---- helpers ----
    def clear(self, color=0x000000):
        c16 = color.to_bytes(2, "big")
        self._set_window(0, 0, self.width - 1, self.height - 1)
        self._cmd(0x2C, c16 * (self.width * self.height))
        self.cs.value(1)

    def on(self):
        self.bl.value(1)

    def off(self):
        self.bl.value(0)
