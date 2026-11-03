from .base import Widget

class TextArea(Widget):
    def __init__(self, x=0, y=0, width=120, height=80, text="", **kwargs):
        super().__init__(x, y, width, height, **kwargs)
        self.text = text
        self.bg_color = kwargs.get("bg_color", 0x0000)
        self.border_color = kwargs.get("border_color", 0xFFFF)
        self.focused = kwargs.get("focused", False)
        self.on_change = kwargs.get("on_change", None)
        self.line_height = 8

    def draw(self, display):
        if not self.visible:
            return
        border = 0xFFFF if self.focused else self.border_color
        display.fill_rectangle(self.x, self.y, self.width, self.height, self.bg_color)
        display.fill_rectangle(self.x, self.y, self.width, 2, border)
        display.fill_rectangle(self.x, self.y+self.height-2, self.width, 2, border)
        display.fill_rectangle(self.x, self.y+2, 2, self.height-4, border)
        display.fill_rectangle(self.x+self.width-2, self.y+2, 2, self.height-4, border)
        lines = self.text.split("\n")
        y = self.y + 4
        for line in lines:
            if y + 8 > self.y + self.height - 4:
                break
            display.text(line, self.x+4, y, self.text_color, 1)
            y += self.line_height

    def update(self, x, y, pressed):
        if not self.enabled or not self.visible:
            return False
        if self.contains(x, y) and pressed:
            self.focused = True
            return True
        return False

    def add_char(self, char):
        if not self.enabled:
            return False
        self.text += char
        if self.on_change:
            self.on_change(self.text)
        return True

    def add_line(self, line):
        if not self.enabled:
            return False
        self.text += "\n" + line
        if self.on_change:
            self.on_change(self.text)
        return True

    def clear(self):
        self.text = ""
        if self.on_change:
            self.on_change(self.text)

    @property
    def value(self):
        return self.text