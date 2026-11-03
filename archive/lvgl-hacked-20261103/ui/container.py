class Container:
    def __init__(self):
        self.widgets = []

    def add(self, widget):
        self.widgets.append(widget)

    def remove(self, widget):
        if widget in self.widgets:
            self.widgets.remove(widget)

    def draw(self, display):
        for w in self.widgets:
            w.draw(display)

    def update(self, x, y, pressed):
        for w in self.widgets:
            if w.update(x, y, pressed):
                return True
        return False