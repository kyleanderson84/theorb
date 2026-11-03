from .base import Widget

class TextField(Widget):
    def __init__(self, x=0, y=0, width=120, height=30, text="", **kwargs):
        super().__init__(x, y, width, height, **kwargs)
        self.text = text
        self.cursor = len(text)
        self.bg_color = kwargs.get("bg_color", 0x0000)
        self.border_color = kwargs.get("border_color", 0xFFFF)
        self.focused = kwargs.get("focused", False)
        self.max_chars = kwargs.get("max_chars", None)
        self.on_change = kwargs.get("on_change", None)

    def draw(self, display):
        if not self.visible:
            return
        border = 0xFFFF if self.focused else self.border_color
        display.fill_rectangle(self.x, self.y, self.width, self.height, self.bg_color)
        display.fill_rectangle(self.x, self.y, self.width, 2, border)
        display.fill_rectangle(self.x, self.y+self.height-2, self.width, 2, border)
        display.fill_rectangle(self.x, self.y+2, 2, self.height-4, border)
        display.fill_rectangle(self.x+self.width-2, self.y+2, 2, self.height-4, border)
        display.text(self.text, self.x+4, self.y+4, self.text_color, 1)
        if self.focused:
            cx = self.x + 4 + len(self.text)*6
            cy = self.y + 4
            display.fill_rectangle(cx, cy, 2, 8, 0xFFFF)

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
        if self.max_chars and len(self.text) >= self.max_chars:
            return False
        self.text = self.text[:self.cursor] + char + self.text[self.cursor:]
        self.cursor += 1
        if self.on_change:
            self.on_change(self.text)
        return True

    def backspace(self):
        if self.cursor > 0:
            self.text = self.text[:self.cursor-1] + self.text[self.cursor:]
            self.cursor -= 1
            if self.on_change:
                self.on_change(self.text)
            return True
        return False

    @property
    def value(self):
        return self.text
