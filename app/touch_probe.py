# touch_probe.py — Diagnose FT6336 touch detection modes.
# Run after a power cycle. Prompts for touch in each mode and reports hits.
# Touch the screen firmly (hold ~2s) during each 5s window.

from machine import I2C, Pin
import time

i2c = I2C(0, scl=Pin(15), sda=Pin(16), freq=400000)
rst = Pin(18, Pin.OUT)
intp = Pin(17, Pin.IN)  # touch INT line


def reset():
    rst(0); time.sleep_ms(10); rst(1); time.sleep_ms(300)


def reg(r):
    return i2c.readfrom_mem(0x38, r, 1)[0]


def wreg(r, v):
    i2c.writeto_mem(0x38, r, bytes([v]))


def probe(label, secs=5):
    print("  [%s] TOUCH NOW for %ds (hold)" % (label, secs))
    hits = 0
    ints = 0
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < secs * 1000:
        try:
            if reg(0x02) != 0:
                hits += 1
            if intp.value() == 0:
                ints += 1
        except OSError:
            pass
        time.sleep_ms(40)
    print("    -> hits=%d int_low=%d" % (hits, ints))
    return hits


print("touch_probe: chip A8=%02x A3=%02x" % (reg(0xA8), reg(0xA3)))
print("reset + test INTERRUPT mode (A4=1, factory default)")
reset()
print("  A4=", reg(0xA4))
probe("INT-mode")

print("switch to POLLING mode (A4=0)")
wreg(0xA4, 0)
time.sleep_ms(50)
print("  A4=", reg(0xA4))
probe("POLL-mode")

print("restore A4=1")
wreg(0xA4, 1)
print("done")
