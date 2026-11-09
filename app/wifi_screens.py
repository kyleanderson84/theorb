# wifi_screens.py — WiFi setup: scan list + password keyboard.
# Flow: Settings -> WiFiScreen (list) -> tap net -> PasswordScreen (keyboard)
#       -> connect + save to config/known_nets.json.

import asyncio
from gui.core.tgui import Screen, ssd
from gui.core.writer import CWriter
from gui.widgets import CloseButton, Label, Button, Listbox, Grid, Pad, Dropdown
import gui.fonts.freesans20 as font
import gui.fonts.font10 as small
from gui.core.colors import (BLACK, GREEN, BLUE, WHITE, RED, YELLOW, CYAN,
                             DARKBLUE, GREY)

wri = CWriter(ssd, font, GREEN, BLACK, verbose=False)
wri_s = CWriter(ssd, small, WHITE, BLACK, verbose=False)

# Keyboard layout rows (lowercase; dropdown swaps to upper/symbols)
_LOWER = (
    "1234567890",
    "qwertyuiop",
    "asdfghjkl_",
    "zxcvbnm.-",
)
_UPPER = tuple(r.upper() for r in _LOWER)
_SYMBOLS = (
    "!@#$%^&*()",
    "-_=+[]{}:;",
    "'\"<>,.?/\\",
    "|~`       ",
)


class WiFiScreen(Screen):
    """List scanned networks. Tap one to connect (password if needed)."""

    def __init__(self):
        super().__init__()
        Label(wri, 2, 2, "WiFi", fgcolor=CYAN, bgcolor=BLACK)
        self.status = Label(wri_s, 22, 2, "scanning...", fgcolor=YELLOW,
                            bgcolor=BLACK)
        CloseButton(wri)
        self.lst = None
        self.loading = False
        self.reg_task(self._scan_task(), on_change=True)

    async def _scan_task(self):
        import wifi
        await asyncio.sleep_ms(50)
        try:
            nets = wifi.scan()
        except Exception as e:
            self.status.value("scan error")
            print("wifi scan err", e)
            return
        if not nets:
            self.status.value("no networks found")
            return
        self._nets = nets
        self.status.value("%d networks" % len(nets))
        labels = []
        for ssid, rssi, auth, known in nets:
            lock = "" if auth == 0 else "*"
            k = "+" if known else " "
            labels.append("%s%s %s" % (k, lock, ssid[:28]))
        self.lst = Listbox(wri, 40, 2, elements=labels, dlines=7,
                           width=300, callback=self._on_select,
                           fgcolor=WHITE, bgcolor=BLACK, select_color=DARKBLUE)

    def _on_select(self, lb):
        idx = lb.value()
        if self._nets and 0 <= idx < len(self._nets):
            ssid, rssi, auth, known = self._nets[idx]
            import wifi
            if auth == 0:
                # Open network: connect directly.
                self.status.value("connecting %s..." % ssid[:16])
                ok, msg = wifi.connect(ssid, "")
                self.status.value(("OK " if ok else "FAIL ") + str(msg)[:18])
                return
            # Known network: try the saved password first; only ask for a new
            # one if that connection fails.
            if known:
                saved = wifi.load_known().get(ssid, "")
                if saved:
                    self.status.value("connecting %s..." % ssid[:16])
                    self.reg_task(self._try_saved(ssid, saved))
                    return
            Screen.change(PasswordScreen, args=(ssid,))

    async def _try_saved(self, ssid, pw):
        import wifi
        try:
            ok, msg = await wifi.aconnect(ssid, pw, save=False)
        except Exception as e:
            ok, msg = False, str(e)
        if ok:
            try:
                self.status.value("OK " + str(msg)[:18])
            except Exception:
                pass
            return
        # Saved password failed: ask for a new one.
        try:
            self.status.value("saved pw failed, enter new")
        except Exception:
            pass
        Screen.change(PasswordScreen, args=(ssid,))


class PasswordScreen(Screen):
    """On-screen keyboard to enter a WiFi password, then connect."""

    def __init__(self, ssid):
        super().__init__()
        self.ssid = ssid
        self.pw = ""
        self.last = (0, 0)
        self.mode = 0  # 0 lower, 1 upper, 2 symbols
        Label(wri_s, 2, 2, "WiFi: " + ssid[:26], fgcolor=CYAN, bgcolor=BLACK)
        # Fixed width (int) so long passwords are not clipped to the initial
        # label width. ~34 chars at font10 width; enough for any WiFi key.
        self.lbl = Label(wri_s, 22, 2, 300, fgcolor=YELLOW, bgcolor=BLACK)
        self._render_pw()
        # Fixed integer width so later .value() calls are not clipped to zero.
        self.status = Label(wri_s, 40, 2, 300, fgcolor=GREEN, bgcolor=BLACK)

        self.rows = 4
        self.cols = 10
        # Use the small font for compact keys that fit 10 cols in 320px.
        # Grid width = cols*(lwidth+4)-4 = 10*(27+4)-4 = 306px.
        colwidth = 27
        self.grid = Grid(wri_s, 60, 7, colwidth, self.rows, self.cols,
                         justify=Label.CENTRE)
        self._populate()
        ch = round(self.grid.height / self.rows)
        cw = round(self.grid.width / self.cols)
        self.pad = Pad(wri_s, 60, 7, height=self.grid.height,
                       width=self.grid.width, callback=self._adjust,
                       args=(ch, cw))
        brow = self.grid.mrow + 5
        dd = Dropdown(wri_s, brow, 2, elements=("abc", "ABC", "sym"),
                      callback=self._ddcb, bdcolor=YELLOW)
        b = Button(wri_s, brow, dd.mcol + 6, text="bsp",
                   callback=self._bsp)
        b = Button(wri_s, brow, b.mcol + 6, text="Connect",
                   fgcolor=WHITE, bgcolor=GREEN, callback=self._connect)
        CloseButton(wri)

    def _layout(self):
        return (_LOWER, _UPPER, _SYMBOLS)[self.mode]

    def _populate(self):
        lay = self._layout()
        for r in range(self.rows):
            for c in range(self.cols):
                self.grid[r, c] = lay[r][c] if c < len(lay[r]) else " "

    def _ddcb(self, dd):
        self.mode = dd.value()
        self._populate()

    def _render_pw(self):
        # Mask all characters except the most recently typed one.
        if self.pw:
            masked = "*" * (len(self.pw) - 1) + self.pw[-1]
        else:
            masked = "_"
        self.lbl.value("pw: " + masked)

    def _adjust(self, pad, ch, cw):
        g = self.grid
        crl, ccl = self.last
        g[crl, ccl] = {"bgcolor": BLACK}
        cr = pad.rr // ch
        cc = pad.rc // cw
        if cr >= self.rows or cc >= self.cols:
            return
        lay = self._layout()
        char = lay[cr][cc] if cc < len(lay[cr]) else ""
        if char and char != " ":
            self.pw += char
            self._render_pw()
        g[cr, cc] = {"bgcolor": RED}
        self.last = (cr, cc)

    def _bsp(self, button):
        if self.pw:
            self.pw = self.pw[:-1]
            self._render_pw()

    def _log(self, msg):
        try:
            with open("/tap.log", "a") as _f:
                _f.write(msg + "\n")
        except Exception:
            pass

    def _force_refresh(self):
        # Push dirty widgets to the panel immediately so status text is
        # visible even while the GUI auto_refresh loop is starved by a
        # blocking sta.connect() call. Best-effort; never raise.
        try:
            Screen.show(False)
            ssd.show()
        except Exception as e:
            self._log("force_refresh EXC: %s" % e)

    def _connect(self, button):
        # Guard against repeated taps spawning duplicate connect tasks.
        if getattr(self, "_busy", False):
            self._log("CONNECT ignored: already busy")
            return
        self._busy = True
        # First thing: give the user INSTANT visible feedback that the tap
        # registered, before anything that could fail or block.
        try:
            button.bgcolor = RED
            button.value("wait...")
        except Exception:
            pass
        try:
            self.status.value("button pressed!")
        except Exception:
            pass
        self._force_refresh()
        self._log("CALLBACK _connect fired ssid=%s pwlen=%d" %
                  (self.ssid, len(self.pw)))
        # Run the (blocking) WiFi connect as a background GUI task so the
        # display and touch keep responding and the status label redraws.
        try:
            self._log("CONNECT set status...")
            self.status.value("connecting...")
            self._log("CONNECT status set OK; scheduling task")
            t = self.reg_task(self._do_connect())
            self._log("CONNECT task scheduled: %r" % t)
        except Exception as e:
            self._log("CONNECT EXC: %s" % e)

    async def _do_connect(self):
        self._log("DO_CONNECT started")
        try:
            import wifi
        except Exception as e:
            self._log("DO_CONNECT import wifi EXC: %s" % e)
            self.status.value("no wifi module")
            return
        self._log("wifi.aconnect exists: %r" % hasattr(wifi, "aconnect"))

        def on_status(phase, detail):
            self._log("on_status %s %s" % (phase, detail))
            try:
                if phase == "start":
                    self.status.value("connecting %s..." % str(detail)[:16])
                elif phase == "ok":
                    self.status.value("connected: " + str(detail)[:18])
                else:
                    self.status.value("failed: " + str(detail)[:20])
            except Exception as e:
                self._log("on_status set EXC: %s" % e)
            self._force_refresh()

        try:
            ok, msg = await wifi.aconnect(self.ssid, self.pw, on_status=on_status)
            self._log("aconnect returned ok=%r msg=%r" % (ok, msg))
            try:
                self.status.value(("OK " if ok else "FAIL ") + str(msg)[:18])
            except Exception:
                pass
            self._force_refresh()
        except Exception as e:
            import sys
            try:
                sys.print_exception(e)
            except Exception:
                pass
            self._log("aconnect EXC: %s" % e)
            try:
                self.status.value("error: " + str(e)[:20])
            except Exception:
                pass
            self._force_refresh()
        finally:
            self._busy = False
