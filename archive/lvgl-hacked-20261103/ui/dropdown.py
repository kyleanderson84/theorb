from .base import Widget

class Dropdown(Widget):
    def __init__(self, x=0, y=0, width=120, height=30, options=None, **kwargs):
        super().__init__(x, y, width, height, **kwargs)
        self.options = options or []
        self.selected = 0
        self.open = False
        self.on_change = kwargs.get("on_change", None)

    def draw(self, display):
        if not self.visible:
            return
        display.fill_rectangle(self.x, self.y, self.width, self.height, 0x0000)
        display.fill_rectangle(self.x, self.y, self.width, 2, 0xFFFF)
        display.fill_rectangle(self.x, self.y+self.height-2, self.width, 2, 0xFFFF)
        display.fill_rectangle(self.x, self.y+2, 2, self.height-4, 0xFFFF)
        display.fill_rectangle(self.x+self.width-2, self.y+2, 2, self.height-4, 0xFFFF)
        if self.options:
            label = self.options[self.selected]
            display.text(label, self.x+4, self.y+4, self.text_color, 1)
            display.text("v", self.x+self.width-10, self.y+4, 0xFFFF, 1)
        if self.open:
            for i, opt in enumerate(self.options):
                oy = self.y + self.height + i * 8
                if oy + 8 > 320:
                    break
                display.fill_rectangle(self.x, oy, self.width, 8, 0x0000)
                display.fill_rectangle(self.x, oy, self.width, 1, 0xFFFF)
                display.text(opt, self.x+4, oy, self.text_color, 1)

    def update(self, x, y, pressed):
        if not self.enabled or not self.visible:
            return False
        if self.contains(x, y) and pressed:
            self.open = not self.open
            return True
        if self.open:
            for i, opt in enumerate(self.options):
                oy = self.y + self.height + i * 8
                if oy + 8 > 320:
                    break
                if self.x <= x < self.x+self.width and oy <= y < oy+8:
                    self.selected = i
                    self.open = False
                    if self.on_change:
                        self.on_change(opt)
                    return True
        return False

    @property
    def value(self):
        return self.options[self.selected] if self.options else None