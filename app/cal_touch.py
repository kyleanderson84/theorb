# cal_touch.py — continuous raw touch readout for calibration.
# Deploy to the board and run:  import cal_touch
# Touch the screen; it prints raw (x, y) for every sample. Tap each corner
# slowly. Ctrl-C to stop. Use the observed min/max to set tpad.init in
# touch_setup.py.

from machine import I2C, Pin
import time

i2c = I2C(0, scl=Pin(15), sda=Pin(16), freq=400000)
rst = Pin(18, Pin.OUT)
rst(0); time.sleep_ms(20); rst(1); time.sleep_ms(150)
print("cal_touch: tap the screen. raw x/y printed below.")


def _run():
    last = None
    while True:
        try:
            if i2c.readfrom_mem(0x38, 0x02, 1)[0] != 0:
                d = i2c.readfrom_mem(0x38, 0x03, 4)
                x = ((d[0] & 0x0F) << 8) | d[1]
                y = ((d[2] & 0x0F) << 8) | d[3]
                if (x, y) != last:
                    print("raw x=%3d y=%3d" % (x, y))
                    last = (x, y)
            else:
                last = None
        except OSError:
            pass
        time.sleep_ms(40)


_run()
