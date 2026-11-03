# cal_visual.py — Visual calibration: shows a crosshair at known screen points,
# captures the RAW touch while you tap it. Works regardless of current tpad mapping.
# Run: import cal_visual   (touch_setup must exist for ssd/framebuf)
# Tap each crosshair when it appears; results print as raw (x,y).

import time
import touch_setup
from gui.core.tgui import ssd

# Screen points to calibrate (row, col) in landscape 320x240 coordinates.
POINTS = [
    ("top-left", 20, 20),
    ("top-right", 20, 300),
    ("bottom-right", 220, 300),
    ("bottom-left", 220, 20),
]


def cross(row, col, length=17, color=0xFFFF):
    ssd.fill_rect(col - length // 2, row, length, 2, color)
    ssd.fill_rect(col, row - length // 2, 2, length, color)


def read_raw(i2c, addr=0x38):
    d = i2c.readfrom_mem(addr, 0x03, 4)
    return (((d[0] & 0x0F) << 8) | d[1], ((d[2] & 0x0F) << 8) | d[3])


def run():
    i2c = touch_setup.i2c
    print("cal_visual: tap each crosshair, LIFT finger between taps")
    results = []
    for name, row, col in POINTS:
        ssd.fill(0x0000)
        cross(row, col)
        ssd.show()
        print("TAP", name, "at screen row", row, "col", col)
        # Capture the first press within the window; hold-sample while pressed.
        got = None
        last = None
        t0 = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), t0) < 12000:
            try:
                if i2c.readfrom_mem(0x38, 0x02, 1)[0] != 0:
                    last = read_raw(i2c)  # keep latest while held
            except OSError:
                pass
            else:
                if last is not None:
                    got = last
                    break
            time.sleep_ms(25)
        if got:
            results.append((name, row, col, got[0], got[1]))
            print("  ->", name, "raw", got)
        else:
            print("  ->", name, "NO TOUCH (skipped)")
    ssd.fill(0x0000)
    ssd.show()
    print("=== RESULTS ===")
    for r in results:
        print("%s screen(r=%d,c=%d) raw(x=%d,y=%d)" % r)
    print("=== END ===")


run()
