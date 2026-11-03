from .base import Widget

class Keyboard(Widget):
    def __init__(self, x=0, y=0, width=320, height=100, **kwargs):
        super().__init__(x, y, width, height, **kwargs)
        self.keys = [
            "1234567890", "qwertyuiop", "asdfghjkl", "zxcvbnm",
            "SPACE", "BACK", "DONE",
        ]
        self.shift = False
        self.on_key = kwargs.get("on_key", None)

    def _key_text(self, k):
        if k == "SPACE":
            return " "
        if k == "BACK":
            return "<"
        if k == "DONE":
            return "OK"
        if self.shift:
            return k.upper()
        return k

    def draw(self, display):
        if not self.visible:
            return
        display.fill_rectangle(self.x, self.y, self.width, self.height, 0x0000)
        display.fill_rectangle(self.x, self.y, self.width, 2, 0xFFFF)
        display.fill_rectangle(self.x, self.y+self.height-2, self.width, 2, 0xFFFF)
        display.fill_rectangle(self.x, self.y+2, 2, self.height-4, 0xFFFF)
        display.fill_rectangle(self.x+self.width-2, self.y+2, 2, self.height-4, 0xFFFF)
        x = self.x + 4
        y = self.y + 4
        for row in self.keys:
            for k in row:
                kw = 40 if k == "SPACE" else 20
                display.fill_rectangle(x, y, kw, 8, 0x07E0)
                display.text(self._key_text(k), x+2, y, 0x0000, 1)
                x += kw + 2
            x = self.x + 4
            y += 10

    def update(self, x, y, pressed):
        if not self.enabled or not self.visible:
            return False
        if not pressed:
            return False
        xk = self.x + 4
        yk = self.y + 4
        for row in self.keys:
            for k in row:
                kw = 40 if k == "SPACE" else 20
                if xk <= x < xk+kw and yk <= y < yk+8:
                    if k == "BACK":
                        if self.on_key:
                            self.on_key("\b")
                    elif k == "DONE":
                        if self.on_key:
                            self.on_key("\n")
                    elif k == "SPACE":
                        if self.on_key:
                            self.on_key(" ")
                    else:
                        if self.on_key:
                            self.on_key(self._key_text(k))
                    return True
                xk += kw + 2
            xk = self.x + 4
            yk += 10
        return False

    @property
    def value(self):
        return None