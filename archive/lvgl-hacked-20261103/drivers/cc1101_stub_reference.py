# -------------------------------------------------
# Minimal CC1101 driver for ESP32‑S3 (SPI)
# -------------------------------------------------
class CC1101:
    def __init__(self, cs, io0, freq=433.92):
        self.cs   = cs
        self.io0  = io0
        self.freq = freq
        print(f"CC1101 init (cs={cs}, io0={io0}, freq={freq} MHz)")

    def status(self):
        # Placeholder – returns a dict with MARCSTATE, RSSI, …
        return {"marcstate": 0, "rssi": 0}