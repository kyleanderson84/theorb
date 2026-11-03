class Widget:
    def __init__(self, x=0, y=0, width=80, height=30, **kwargs):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.visible = kwargs.get("visible", True)
        self.enabled = kwargs.get("enabled", True)
        self.focused = kwargs.get("focused", False)
        self.text_color = kwargs.get("text_color", 0xFFFF)
        self.on_event = kwargs.get("on_event", None)

    def contains(self, x, y):
        return (self.x <= x < self.x + self.width and
                self.y <= y < self.y + self.height)

    def draw(self, display):
        pass

    def update(self, x, y, pressed):
        return False

    @property
    def value(self):
        return None
