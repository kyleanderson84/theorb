from ui import (
    Button, Checkbox, RadioGroup, Radio, TextField, TextArea,
    Dropdown, Keyboard, Container,
)
import ili9341, machine, time, ft6x36

d = ili9341.Display()
i2c = machine.I2C(scl=machine.Pin(15), sda=machine.Pin(16))
t = ft6x36.FT6336(i2c=i2c)

c = Container()

b = Button(10, 10, 80, 40, "OK", color=0x07E0, pressed_color=0xFFFF)
c.add(b)

cb = Checkbox(10, 60, 30, 30, "On", checked=False)
c.add(cb)

grp = RadioGroup()
r1 = Radio(100, 60, 30, 30, "A", group=grp)
r2 = Radio(150, 60, 30, 30, "B", group=grp)
grp.add(r1); grp.add(r2)
c.add(r1); c.add(r2)

tf = TextField(10, 110, 150, 30, text="input")
c.add(tf)

ta = TextArea(10, 160, 150, 50, text="multiline\ninfo")
c.add(ta)

dd = Dropdown(10, 230, 140, 30, options=["One","Two","Three"])
c.add(dd)

kb = Keyboard(0, 290, width=320, height=40)
c.add(kb)

d.clear(0x0000)
d.text("TouchUI Test", 70, 5, 0xFFFF, 2)
c.draw(d)

try:
    while True:
        if t.scan():
            x, y = t.position()
            c.update(x, y, True)
        time.sleep_ms(30)
except KeyboardInterrupt:
    pass
d.clear(0x0000)
print("done")