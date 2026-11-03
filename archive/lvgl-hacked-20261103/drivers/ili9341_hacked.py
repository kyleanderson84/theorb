import time

import framebuf
from machine import Pin, SPI


class Display:
    WIDTH = 320
    HEIGHT = 240

    def __init__(
        self,
        cs=10,
        dc=46,
        bl=45,
        spi=None,
        width=320,
        height=240,
        rotation=1,
        baudrate=40000000,
    ):
        self.width = width
        self.height = height
        self.rotation = rotation

        self.cs = cs if isinstance(cs, Pin) else Pin(cs, Pin.OUT, value=1)
        self.dc = dc if isinstance(dc, Pin) else Pin(dc, Pin.OUT, value=1)
        self.bl = None if bl is None else (bl if isinstance(bl, Pin) else Pin(bl, Pin.OUT, value=1))

        if spi is None:
            spi = SPI(
                1,
                baudrate=baudrate,
                polarity=0,
                phase=0,
                sck=Pin(12),
                mosi=Pin(11),
            )
        self.spi = spi

        self._chunk = bytes(512)

        self._init()

    def _wcmd(self, cmd):
        self.cs(0)
        self.dc(0)
        self.spi.write(bytes([cmd]))
        self.cs(1)

    def _wdata(self, data):
        self.cs(0)
        self.dc(1)
        self.spi.write(data)
        self.cs(1)

    def _wreg(self, cmd, data):
        self.cs(0)
        self.dc(0)
        self.spi.write(bytes([cmd]))
        self.dc(1)
        self.spi.write(data)
        self.cs(1)

    def _init(self):
        self._wcmd(0x01)
        time.sleep_ms(120)
        self._wreg(0x3A, b"\x55")
        self._wcmd(0x21)
        self._wcmd(0x11)
        time.sleep_ms(120)

        self._wreg(0xCF, b"\x00\xc1\x30")
        self._wreg(0xED, b"\x64\x03\x12\x81")
        self._wreg(0xE8, b"\x85\x00\x78")
        self._wreg(0xCB, b"\x39\x2c\x00\x34\x02")
        self._wreg(0xF7, b"\x20")
        self._wreg(0xEA, b"\x00\x00")
        self._wreg(0xC0, b"\x23")
        self._wreg(0xC1, b"\x10")
        self._wreg(0xC5, b"\x3e\x28")
        self._wreg(0xC7, b"\x86")
        self._wcmd(0x36)
        self._wdata(bytes([self._madctl()]))
        self._wreg(0xB1, b"\x00\x18")
        self._wreg(0xB6, b"\x08\x82\x27")
        self._wcmd(0xF2)
        self._wdata(b"\x00")
        self._wreg(0x26, b"\x01")
        self._wcmd(0xE0)
        self._wdata(
            b"\x0f\x31\x2b\x0c\x0e\x08\x4e\xf1\x37\x07\x10\x03\x0e\x09\x00"
        )
        self._wcmd(0xE1)
        self._wdata(
            b"\x00\x0e\x14\x03\x11\x07\x31\xc1\x48\x08\x0f\x0c\x31\x36\x0f"
        )
        self._wcmd(0x11)
        time.sleep_ms(120)
        self._wcmd(0x29)
        time.sleep_ms(50)
        if self.bl is not None:
            self.bl(1)

    def _madctl(self):
        if self.rotation == 1:
            return 0x28
        if self.rotation == 2:
            return 0xC8
        if self.rotation == 3:
            return 0xE8
        return 0x48

    def set_rotation(self, rotation):
        self.rotation = rotation
        self._wcmd(0x36)
        self._wdata(bytes([self._madctl()]))

    def _set_window(self, x0, y0, x1, y1):
        self.cs(0)
        self.dc(0)
        self.spi.write(b"\x2a")
        self.dc(1)
        self.spi.write(bytes([x0 >> 8, x0 & 0xFF, x1 >> 8, x1 & 0xFF]))
        self.dc(0)
        self.spi.write(b"\x2b")
        self.dc(1)
        self.spi.write(bytes([y0 >> 8, y0 & 0xFF, y1 >> 8, y1 & 0xFF]))
        self.dc(0)
        self.spi.write(b"\x2c")
        self.dc(1)
        self.cs(1)

    def fill_rectangle(self, x, y, w, h, colour=0xFFFF):
        if w <= 0 or h <= 0:
            return
        x1 = min(x + w - 1, self.width - 1)
        y1 = min(y + h - 1, self.height - 1)
        x = max(x, 0)
        y = max(y, 0)
        if x > x1 or y > y1:
            return
        self._set_window(x, y, x1, y1)
        self.cs(0)
        self.dc(1)
        c = bytes([colour >> 8, colour & 0xFF])
        chunk = c * 256
        remaining = (x1 - x + 1) * (y1 - y + 1)
        while remaining > 0:
            n = 256 if remaining > 256 else remaining
            self.spi.write(chunk[: n * 2])
            remaining -= n
        self.cs(1)

    fill = fill_rectangle

    def clear(self, colour=0x0000):
        self.fill_rectangle(0, 0, self.width, self.height, colour)

    def pixel(self, x, y, colour):
        if 0 <= x < self.width and 0 <= y < self.height:
            self.fill_rectangle(x, y, 1, 1, colour)

    def text(self, string, x, y, colour=0xFFFF, scale=2, bg=None):
        w = len(string) * 8
        h = 8
        buf = bytearray((w * h) // 8)
        fb = framebuf.FrameBuffer(buf, w, h, framebuf.MONO_HLSB)
        fb.fill(0)
        fb.text(string, 0, 0, 1)
        if bg is not None:
            self.fill_rectangle(x, y, w * scale, h * scale, bg)
        for yy in range(h):
            for xx in range(w):
                if fb.pixel(xx, yy):
                    self.fill_rectangle(
                        x + xx * scale, y + yy * scale, scale, scale, colour
                    )

    def invert(self, on=True):
        self._wcmd(0x20 if not on else 0x21)

    def on(self):
        self._wcmd(0x29)

    def off(self):
        self._wcmd(0x28)
