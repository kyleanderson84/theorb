# screens.py — Orb screens: main menu + agent status.
# The status screen hosts the frozen Supervisor as a GUI background task, so the
# agent loop runs alongside touch handling and screen refresh.

from gui.core.tgui import Screen, ssd
from gui.core.writer import CWriter
from gui.widgets import Menu, CloseButton, Label
import gui.fonts.freesans20 as font
import gui.fonts.font10 as small_font
from gui.core.colors import BLACK, GREEN, BLUE, WHITE, RED, YELLOW, CYAN

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
    def __init__(self):
        super().__init__()
        apps = (
            ("Agent", self._open_agent, ()),
            ("Radio", self._open_detail, ("Radio",)),
            ("Sub-GHz", self._open_detail, ("Sub-GHz",)),
            ("NFC", self._open_detail, ("NFC",)),
            ("IR", self._open_detail, ("IR",)),
            ("Settings", self._open_detail, ("Settings",)),
        )
        Menu(wri, bgcolor=BLUE, textcolor=WHITE, fgcolor=RED, args=(("Apps", apps),))
        CloseButton(wri)

    def _open_agent(self, button):
        Screen.change(AgentScreen)

    def _open_detail(self, button, title):
        Screen.change(DetailScreen, args=(title,))


class DetailScreen(Screen):
    def __init__(self, title):
        super().__init__()
        Label(wri, 60, 2, title, fgcolor=YELLOW, bgcolor=BLACK)
        Label(wri, 100, 2, "Not implemented yet", fgcolor=WHITE, bgcolor=BLACK)
        CloseButton(wri)
