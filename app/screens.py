# screens.py — Orb screens: main menu + agent status.
# The status screen hosts the frozen Supervisor as a GUI background task, so the
# agent loop runs alongside touch handling and screen refresh.

from gui.core.tgui import Screen, ssd
from gui.core.writer import CWriter
from gui.widgets import CloseButton, Label, Button, HorizSlider
import gui.fonts.freesans20 as font
import gui.fonts.font10 as small_font
from gui.core.colors import (BLACK, GREEN, BLUE, WHITE, RED, YELLOW, CYAN,
                             DARKBLUE, GREY)

wri = CWriter(ssd, font, GREEN, BLACK, verbose=False)
wri_s = CWriter(ssd, small_font, WHITE, BLACK, verbose=False)


class AgentScreen(Screen):
    """Live view of the supervisor's state + a log tail."""

    _status = "idle"  # class-level: survives the supervisor writing to it

    def __init__(self):
        super().__init__()
        self.lbl_state = Label(wri, 10, 2, "state: ---", fgcolor=YELLOW, bgcolor=BLACK)
        self.lbl_epoch = Label(wri_s, 40, 2, "epoch: -", fgcolor=CYAN, bgcolor=BLACK)
        self.lbl_log = Label(wri_s, 70, 2, "", fgcolor=WHITE, bgcolor=BLACK)
        CloseButton(wri)
        self._last = None

        # Start the frozen supervisor as a background task bound to this screen.
        from agent import Supervisor
        self._sup = Supervisor(gui_status=self._on_status, hw={})
        self.reg_task(self._sup.run())
        self.reg_task(self._ui_refresh(), on_change=True)

    def _on_status(self, text):
        # Called from the supervisor coroutine - just stash, UI task renders.
        AgentScreen._status = text

    async def _ui_refresh(self):
        import asyncio
        while True:
            s = AgentScreen._status
            if s != self._last:
                self.lbl_state.value("state: %s" % s)
                self.lbl_epoch.value("epoch: %d" % self._sup.epoch)
                self._last = s
            await asyncio.sleep_ms(250)

    def on_hide(self):
        try:
            self._sup.stop()
        except Exception:
            pass


class BaseScreen(Screen):
    """2-column grid launcher (Flipper-style). 320x240 landscape."""

    # (label, callback-name) laid out row-major, 2 per row.
    APPS = (
        ("Agent", "agent"),
        ("Radio", "Radio"),
        ("Sub-GHz", "Sub-GHz"),
        ("NFC", "NFC"),
        ("IR", "IR"),
        ("Settings", "Settings"),
    )

    def __init__(self):
        super().__init__()
        Label(wri, 2, 2, "THE ORB", fgcolor=CYAN, bgcolor=BLACK)
        # Grid geometry: 2 cols x 3 rows below the title bar (y≈24px).
        cw, ch = 150, 50          # cell width / height
        x0, y0 = 6, 24
        for i, (label, target) in enumerate(self.APPS):
            r, c = divmod(i, 2)
            x = x0 + c * (cw + 8)
            y = y0 + r * (ch + 6)
            Button(wri, y, x, height=ch, width=cw, text=label,
                   fgcolor=WHITE, bgcolor=DARKBLUE, textcolor=WHITE,
                   callback=self._on_app, args=(target,))
        CloseButton(wri)
        # Bottom status bar: battery. font10 is 17px tall; place near y=218.
        # Integer width (92px) so texts up to 'CHG 100%' (83px) never clip.
        # Fixed-width via battery.fixed_status keeps redraws from leaving
        # stale pixels; the integer width prevents truncation.
        self.lbl_batt = Label(wri_s, 218, 2, 92, fgcolor=GREEN, bgcolor=BLACK)
        self.reg_task(self._status_loop(), on_change=True)

    async def _status_loop(self):
        import asyncio
        try:
            import battery
        except Exception:
            battery = None
        while True:
            if battery:
                self.lbl_batt.value(battery.fixed_status())
            else:
                self.lbl_batt.value("USB power   ")
            await asyncio.sleep_ms(10000)

    def _on_app(self, button, target):
        if target == "agent":
            Screen.change(AgentScreen)
        elif target == "Settings":
            Screen.change(SettingsScreen)
        else:
            Screen.change(DetailScreen, args=(target,))


class DetailScreen(Screen):
    def __init__(self, title):
        super().__init__()
        Label(wri, 60, 2, title, fgcolor=YELLOW, bgcolor=BLACK)
        Label(wri, 100, 2, "Not implemented yet", fgcolor=WHITE, bgcolor=BLACK)
        CloseButton(wri)


class SettingsScreen(Screen):
    """WiFi, brightness, and power-off."""

    def __init__(self):
        super().__init__()
        Label(wri, 2, 2, "Settings", fgcolor=CYAN, bgcolor=BLACK)

        try:
            import power
        except Exception:
            power = None

        # --- WiFi row (lowered ~14px to clear the CloseButton X) ---
        Label(wri, 40, 2, "WiFi", fgcolor=WHITE, bgcolor=BLACK)
        try:
            import wifi
            wtext = wifi.current_ssid() or "not connected"
        except Exception:
            wtext = "unavailable"
        self.lbl_wifi = Label(wri_s, 40, 80, wtext[:26], fgcolor=GREEN,
                              bgcolor=BLACK)
        Button(wri, 36, 240, height=24, width=68, text="Setup",
               fgcolor=WHITE, bgcolor=DARKBLUE, callback=self._open_wifi)

        # --- Brightness ---
        cur = power.get_brightness() if power else 100
        Label(wri, 76, 2, "Brightness", fgcolor=WHITE, bgcolor=BLACK)
        self.lbl_val = Label(wri_s, 76, 200, "%d%%" % cur, fgcolor=YELLOW,
                             bgcolor=BLACK)

        def on_slider(slider):
            pct = int(round(slider.value() * 100))
            self.lbl_val.value("%d%%" % pct)
            if power:
                power.set_brightness(pct)

        HorizSlider(wri, 98, 20, width=280, divisions=10,
                    fgcolor=GREEN, bgcolor=DARKBLUE, slotcolor=GREY,
                    value=cur / 100, callback=on_slider)

        # --- Power ---
        Button(wri, 138, 85, height=44, width=150, text="Power Off",
               fgcolor=WHITE, bgcolor=RED, textcolor=WHITE,
               callback=self._confirm_power_off)
        CloseButton(wri)

    def _open_wifi(self, button):
        from wifi_screens import WiFiScreen
        Screen.change(WiFiScreen)

    def _confirm_power_off(self, button):
        # Ask before shutting down so a stray tap can't power off the device.
        from gui.widgets import DialogBox
        kwargs = {
            "writer": wri,
            "row": 60,
            "col": 40,
            "elements": (("Yes", RED), ("No", GREEN)),
            "label": "Power off?",
            "bgcolor": DARKBLUE,
            "callback": self._power_off_result,
        }
        Screen.change(DialogBox, kwargs=kwargs)

    def _power_off_result(self, window, *args):
        if window.value() == "Yes":
            self._power_off(None)

    def _power_off(self, button):
        try:
            import power
            power.power_off()
        except Exception as e:
            print("power off failed:", e)
