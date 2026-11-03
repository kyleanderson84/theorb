import time
import machine

import ili9341
import ft6x36
from ui import Button, Checkbox

spi = machine.SPI(1, baudrate=40_000_000, polarity=0, phase=0,
                  sck=machine.Pin(12), mosi=machine.Pin(11))
d = ili9341.Display(cs=10, dc=46, bl=45, spi=spi, rotation=1)

i2c = machine.I2C(scl=machine.Pin(15), sda=machine.Pin(16))
t = ft6x36.FT6336(i2c=i2c)

clicks = 0
state = {"btn": 0, "cb": False}


def on_click():
    state["btn"] += 1
    d.text("clicks: %d" % state["btn"], 240, 120, 0x07FF, 2)


def on_change(v):
    state["cb"] = v
    d.invert(v)
    d.text("invert %s" % ("on" if v else "off"), 240, 180, 0xFFE0, 1)


b1 = Button(20, 80, 100, 40, "Click!", color=0x07E0, pressed_color=0xFFFF, on_click=on_click)
b2 = Button(20, 140, 100, 40, "Dead", color=0xF800)
cb = Checkbox(140, 80, 30, 30, "Inv", checked=False, on_change=on_change)

c = [b1, b2, cb]

d.clear(0x0000)
d.text("Touch Test", 90, 10, 0xFFFF, 2)
d.text("clicks: 0", 240, 120, 0x07FF, 2)
d.text("invert off", 240, 180, 0xFFE0, 1)
for w in c:
    w.draw(d)

print("touch-gui started; tap the green button and checkbox")
last = None
pressed = False
try:
    while True:
        n = t.scan()
        if n:
            x, y = t.position()
            hit = False
            for w in c:
                if w.update(x, y, True):
                    hit = True
            if hit:
                for w in c:
                    w.draw(d)
            if (x, y) != last:
                d.pixel(x, y, 0xF81F)
                last = (x, y)
            pressed = True
        elif pressed:
            for w in c:
                w.update(-1, -1, False)
            pressed = False
        time.sleep_ms(20)
except KeyboardInterrupt:
    pass
d.clear(0x0000)
print("touch-gui done, clicks=%d, invert=%s" % (state["btn"], state["cb"]))
