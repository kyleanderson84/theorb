from .base import Widget

class Button(Widget):
    def __init__(self, x=0, y=0, width=80, height=30, text="", **kwargs):
        super().__init__(x, y, width, height, **kwargs)
        self.text = text
        self.color = kwargs.get("color", 0x07E0)
        self.pressed_color = kwargs.get("pressed_color", 0xFFFF)
        self.pressed = False
        self.on_click = kwargs.get("on_click", None)

    def draw(self, display):
        if not self.visible:
            return
        c = self.pressed_color if self.pressed else self.color
        display.fill_rectangle(self.x, self.y, self.width, self.height, c)
        display.fill_rectangle(self.x+2, self.y+2, self.width-4, self.height-4, 0x0000)
        tx = self.x + max(0, self.width//2 - len(self.text)*4)
        ty = self.y + max(0, self.height//2 - 4)
        display.text(self.text, tx, ty, self.text_color, 1)

    def update(self, x, y, pressed):
        if not self.enabled or not self.visible:
            return False
        if self.contains(x, y):
            self.pressed = pressed
            if pressed and self.on_click:
                self.on_click()
            return True
        if not pressed:
            self.pressed = False
        return False

    @property
    def value(self):
        return self.pressed
