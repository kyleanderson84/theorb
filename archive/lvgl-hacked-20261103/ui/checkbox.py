from .base import Widget

class Checkbox(Widget):
    def __init__(self, x=0, y=0, width=30, height=30, label="", checked=False, **kwargs):
        super().__init__(x, y, width, height, **kwargs)
        self.label = label
        self.checked = checked
        self.on_change = kwargs.get("on_change", None)
        self.box_color = kwargs.get("box_color", 0xFFFF)
        self.check_color = kwargs.get("check_color", 0x07E0)

    def draw(self, display):
        if not self.visible:
            return
        display.fill_rectangle(self.x, self.y, self.width, self.height, self.box_color)
        display.fill_rectangle(self.x+2, self.y+2, self.width-4, self.height-4, 0x0000)
        if self.checked:
            cx = self.x + self.width//2
            cy = self.y + self.height//2
            display.fill_rectangle(cx-2, cy-2, 4, 4, self.check_color)
        lx = self.x + self.width + 4
        display.text(self.label, lx, self.y + self.height//2 - 4, self.text_color, 1)

    def update(self, x, y, pressed):
        if not self.enabled or not self.visible:
            return False
        if self.contains(x, y) and pressed:
            self.checked = not self.checked
            if self.on_change:
                self.on_change(self.checked)
            return True
        return False

    @property
    def value(self):
        return self.checked
