# ft6206.py Capacitive touch driver

# Released under the MIT License (MIT). See LICENSE.
# Copyright (c) 2024 Peter Hinch

# It is minimal, providing only the required functionality for the touh GUI.
# Sources: datasheet, Adafruit driver
# https://github.com/adafruit/Adafruit_FT6206_Library/tree/master

# I2C clock rate 10KHz - 400KHz
# Can read multiple bytes (page 20)
# Section 3.1.3 Number of touch points: 1-2 is valid (as per Adafruit)

# 0 <= x <= 240
# 0 <= y <= 320

from .touch import ABCTouch


class FT6206(ABCTouch):
    def __init__(self, i2c, ssd, addr=0x38, thresh=128):
        super().__init__(ssd, None)  # No preprocessor required
        self.i2c = i2c
        self.addr = addr
        self._fails = 0
        self._reset_cb = None  # set by touch_setup to recover a wedged chip
        buf = bytearray(1)
        buf[0] = thresh
        self.i2c.writeto_mem(addr, 0x80, buf)  # Set touch threshold
        self.i2c.readfrom_mem_into(addr, 0xA8, buf)
        if ok := (buf[0] == 0x11):
            self.i2c.readfrom_mem_into(addr, 0xA3, buf)
            ok = buf[0] in (0x06, 0x36, 0x64)
        if not ok:
            raise OSError("Invalid FT6206 chip type.")

    def reset(self, rst_pin, delay_ms=10, settle_ms=300):
        """Hardware reset the touch controller and restore config.
        On the ES3C28P the FT6336 locks up under I2C error storms; a reset
        pulse (LOW 10ms, HIGH 300ms — matches Bruce) brings it back."""
        rst_pin(0)
        import time
        time.sleep_ms(delay_ms)
        rst_pin(1)
        time.sleep_ms(settle_ms)
        try:
            self.i2c.writeto_mem(self.addr, 0x80, bytearray(b"\x80"))
        except OSError:
            pass
        self._fails = 0

    def _value(self, offs, buf=bytearray(1)):
        i2c.readfrom_mem_into(addr, offs, buf)  # b0..b3 = MSB
        ev = buf[0] & 0xC0  # Event: 0 == touch, 0x40 release. Consider this ??
        v = (buf[0] & 0x0F) << 8
        i2c.readfrom_mem_into(addr, offs + 1, buf)  # LSB
        return v | buf[0]

    # If touched, populate ._x and ._y with raw data. Return True.  ** returns 0 <= y <= 320, 0 <= x <= 240
    # If not touched return False.
    def acquire(self, buf=bytearray(11)):
        addr = self.addr
        i2c = self.i2c
        # This board's I2C occasionally NAKs / the FT6336 locks up under error
        # storms. Retry, and after sustained failure call the reset callback
        # (if provided) to recover, then report "not touched" so the GUI's
        # touch-test task never dies.
        for _ in range(3):
            try:
                i2c.readfrom_mem_into(addr, 0x02, buf)
                self._fails = 0
                break
            except OSError:
                continue
        else:
            self._fails += 1
            if self._fails >= 5 and self._reset_cb is not None:
                self._fails = 0
                try:
                    self._reset_cb()
                except Exception:
                    pass
            return False
        t = buf[0]
        if t == 1:  # One touch
            if buf[1] & 0x40:
                return False  # The only touch was a release
        if t > 2 or t == 0:  # No touch or invalid
            return False
        # We have at least one valid touch
        if (t == 2) and ((buf[7] & 0x40) == 0):  # Touch 2 was a press
            self._x = ((buf[7] & 0x0F) << 8) | buf[8]  # Save 2nd touch
            self._y = ((buf[9] & 0x0F) << 8) | buf[10]  # Don't care about touch 1
        else:  # Either t == 1 with a valid 1st touch or touch 2 was a release
            if buf[1] & 0x40:  # Both touches were releases (is this possible?)
                return False
            self._x = ((buf[1] & 0x0F) << 8) | buf[2]  # Save 1st touch
            self._y = ((buf[3] & 0x0F) << 8) | buf[4]
        return True
