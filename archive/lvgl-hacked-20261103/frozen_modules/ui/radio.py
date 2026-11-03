from .base import Widget

class RadioGroup:
    def __init__(self):
        self.radios = []
        self.selected = None
        self.on_change = None

    def add(self, radio):
        self.radios.append(radio)
        radio.group = self
        if self.selected is None:
            self.selected = radio
            radio.checked = True

    def select(self, radio):
        for r in self.radios:
            r.checked = False
        radio.checked = True
        self.selected = radio
        if self.on_change:
            self.on_change(radio.label)

class Radio(Widget):
    def __init__(self, x=0, y=0, width=30, height=30, label="", checked=False, **kwargs):
        super().__init__(x, y, width, height, **kwargs)
        self.label = label
        self.checked = checked
        self.group = kwargs.get("group", None)
        self.on_change = kwargs.get("on_change", None)

    def draw(self, display):
        if not self.visible:
            return
        cx = self.x + self.width//2
        cy = self.y + self.height//2
        display.fill_rectangle(self.x, self.y, self.width, self.height, 0xFFFF)
        display.fill_rectangle(self.x+2, self.y+2, self.width-4, self.height-4, 0x0000)
        if self.checked:
            display.fill_rectangle(cx-3, cy-3, 6, 6, 0x07E0)
        lx = self.x + self.width + 4
        display.text(self.label, lx, cy-4, self.text_color, 1)

    def update(self, x, y, pressed):
        if not self.enabled or not self.visible:
            return False
        if self.contains(x, y) and pressed and self.group:
            self.group.select(self)
            if self.on_change:
                self.on_change(self.label)
            return True
        return False

    @property
    def value(self):
        return self.checked
