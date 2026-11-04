# subghz_screens.py — Sub-GHz (CC1101) scanner, OOK capture, and capture browser.
#
# Flow:
#   Launcher -> Sub-GHz: live RSSI for 315 / 433.92 / 868 MHz.
#     Tap a band, then press a remote during the listen window -> raw OOK capture,
#     decoded in place. "Save" persists it; "Files" opens the capture browser.
#   Files (SavedScreen) -> tap a capture -> CaptureScreen: metadata + protocol
#     guess + hex dump + Delete.
#
# The CC1101 is an external SPI module shared with the agent payload via
# cc1101.open_radio(); decoding + storage live in frozen/modules/subghz.py.
# See docs/HARDWARE_REFERENCE.md for wiring (GDO pins stay tri-stated: they
# share the I2C bus, so receive is FIFO-based and we never RF-transmit).

import asyncio
import time
from gui.core.tgui import Screen, display, ssd
from gui.core.writer import CWriter
from gui.widgets import CloseButton, Label, Button
import gui.fonts.freesans20 as font
import gui.fonts.font10 as small
from gui.core.colors import (BLACK, GREEN, BLUE, WHITE, RED, YELLOW, CYAN,
                             DARKBLUE, GREY)
import subghz

wri = CWriter(ssd, font, GREEN, BLACK, verbose=False)
wri_s = CWriter(ssd, small, WHITE, BLACK, verbose=False)

BANDS = ((315.0, "315.0"), (433.92, "433.9"), (868.0, "868.0"))
LISTEN_MS = 4000
MAX_LIST = 5


def _sym_us():
    try:
        import cc1101
        return cc1101.open_radio().symbol_us() or 10.0
    except Exception:
        return 10.0


class SubGhzScreen(Screen):
    """Sweep the common sub-GHz bands, show live RSSI, capture + decode OOK."""

    def __init__(self):
        super().__init__()
        Label(wri, 2, 2, "Sub-GHz", fgcolor=CYAN, bgcolor=BLACK)
        self.status = Label(wri_s, 24, 2, "init radio...", fgcolor=YELLOW,
                            bgcolor=BLACK)
        self._rows = []
        for i, (f, name) in enumerate(BANDS):
            y = 44 + i * 20
            Label(wri_s, y, 2, "%s MHz" % name, fgcolor=WHITE, bgcolor=BLACK)
            self._rows.append(Label(wri_s, y, 120, "--- dBm",
                                    fgcolor=GREEN, bgcolor=BLACK))
        self.peak = Label(wri_s, 104, 2, "peak: ---", fgcolor=YELLOW,
                          bgcolor=BLACK)
        self.cap = Label(wri_s, 122, 2, "tap a band, then press the remote",
                         fgcolor=CYAN, bgcolor=BLACK)
        self.dec = Label(wri_s, 140, 2, "", fgcolor=GREEN, bgcolor=BLACK)

        self._scanning = False
        self._capture_band = None
        self._radio = None
        self._last = None
        self._last_freq = None
        self._last_peak = None

        for i, (f, name) in enumerate(BANDS):
            Button(wri, 158, 2 + i * 106, height=34, width=104,
                   text=name + " MHz", fgcolor=WHITE, bgcolor=DARKBLUE,
                   textcolor=WHITE, callback=self._on_band, args=(f,))
        Button(wri_s, 198, 2, height=38, width=150, text="Save",
               fgcolor=WHITE, bgcolor=BLUE, textcolor=WHITE,
               callback=self._on_save)
        Button(wri_s, 198, 168, height=38, width=150, text="Files",
               fgcolor=WHITE, bgcolor=DARKBLUE, textcolor=WHITE,
               callback=self._on_files)
        CloseButton(wri)
        self._start_scan()

    def _start_scan(self):
        self._scanning = True
        self.reg_task(self._scan_loop(), on_change=True)

    def after_open(self):
        # Returning from the capture browser: restart the cancelled scan task.
        if not self._scanning:
            self._start_scan()

    async def _scan_loop(self):
        import cc1101
        self._radio = cc1101.open_radio()
        if not self._radio.present():
            self.status.value("no CC1101 found")
            self.cap.value("check SPI: SCK2 MOSI14 MISO3 CS21")
            return
        self.status.value("scanning 315 / 433.92 / 868")
        self._radio.config_ook(BANDS[1][0])

        while self._scanning:
            if self._capture_band is not None:
                f = self._capture_band
                self._capture_band = None
                await self._do_capture(f)
                continue

            best_dbm, best_f, best_name = -999, BANDS[1][0], "433.9"
            for i, (f, name) in enumerate(BANDS):
                self._radio.set_freq(f)
                self._radio.rx()
                await asyncio.sleep_ms(45)
                dbm = self._radio.rssi_dbm()
                self._rows[i].value("%4d dBm" % dbm)
                if dbm > best_dbm:
                    best_dbm, best_f, best_name = dbm, f, name
                self._radio.idle()
                await asyncio.sleep_ms(5)
            self.peak.value("peak: %s MHz  %d dBm" % (best_name, best_dbm))

    async def _do_capture(self, freq):
        radio = self._radio
        self.status.value("listening %.2f MHz - press remote" % freq)
        self.cap.value("listening...")
        self.dec.value("")
        radio.set_freq(freq)
        radio.rx()
        # Drain continuously: infinite-FIFO OOK overflows in ~5 ms otherwise.
        floor = 127
        peak = -999
        t0 = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), t0) < 40:   # cal + ambient floor
            n = radio.rx_bytes()
            if n:
                radio.read_rx_fifo(n)         # discard cal/idle bytes
            dbm = radio.rssi_dbm()
            if dbm < floor:
                floor = dbm
            if dbm > peak:
                peak = dbm
            await asyncio.sleep_ms(1)
        thresh = max(floor + 6, -90)
        self.cap.value("listening... floor %d dBm" % floor)

        buf = bytearray()
        hot = False
        last_hot = None
        end = time.ticks_add(time.ticks_ms(), LISTEN_MS)
        while time.ticks_diff(end, time.ticks_ms()) > 0 and self._scanning:
            n = radio.rx_bytes()
            if n:
                chunk = radio.read_rx_fifo(min(n, 64))
                if hot:
                    buf += chunk
                    if len(buf) >= 8192:
                        break
            dbm = radio.rssi_dbm()
            if dbm > peak:
                peak = dbm
            if not hot:
                if dbm > thresh:
                    hot = True
                    last_hot = time.ticks_ms()
                await asyncio.sleep_ms(1)
                continue
            if dbm >= thresh - 4:
                last_hot = time.ticks_ms()
            elif last_hot is not None and time.ticks_diff(
                    time.ticks_ms(), last_hot) > 25:
                break                         # ~25 ms of quiet ends the burst
            await asyncio.sleep_ms(0)          # drain hard while a burst is on
        radio.idle()

        self.status.value("scanning 315 / 433.92 / 868")
        data = bytes(buf)
        if not data or subghz.analyse(data)[1] == 0:
            self._last = None
            self.cap.value("%.1fM: no burst (peak %d dBm)" % (freq, peak))
            return

        self._last = data
        self._last_freq = freq
        self._last_peak = peak
        self.cap.value("%.1fM %dB peak %d dBm" % (freq, len(data), peak))
        self._show_decode(data)

    def _show_decode(self, data):
        res = subghz.decode(data, _sym_us())
        g = res["guess"]
        if g:
            self.dec.value("%s %s (%db)" % (g["protocol"], g["hex"], g["bits"]))
        elif res.get("noise"):
            self.dec.value("noisy/weak - try closer/nearer")
        else:
            self.dec.value("no match, unit~%dus %druns" %
                           (int(res["unit_us"]), res["runs"]))
        return res

    def _on_band(self, button, freq):
        if self._capture_band is None:
            self._capture_band = freq

    def _on_save(self, button):
        if not self._last:
            self.status.value("nothing to save")
            return
        try:
            name = subghz.save_capture(self._last, self._last_freq,
                                       self._last_peak, _sym_us())
            self.status.value("saved %s" % name)
        except Exception as e:
            self.status.value("save failed: %r" % e)

    def _on_files(self, button):
        Screen.change(SavedScreen)

    def on_hide(self):
        self._scanning = False
        try:
            if self._radio:
                self._radio.idle()
        except Exception:
            pass


class SavedScreen(Screen):
    """Browse captures saved under /captures."""

    def __init__(self):
        super().__init__()
        Label(wri, 2, 2, "Captures", fgcolor=CYAN, bgcolor=BLACK)
        self._rows = []
        CloseButton(wri)

    def after_open(self):
        # Rebuilt every time (after saving / deleting) in case files changed.
        for w in self._rows:
            try:
                self.displaylist.remove(w)
                self.lstactive.remove(w)
            except ValueError:
                pass
        self._rows = []
        display.fill_rect(2, 24, 316, 210, BLACK)

        caps = subghz.list_captures()[-MAX_LIST:]
        if not caps:
            self._rows.append(Label(wri_s, 60, 2, "no captures yet",
                                    fgcolor=WHITE, bgcolor=BLACK))
            self._rows.append(Label(wri_s, 80, 2,
                                    "capture on Sub-GHz, then Save",
                                    fgcolor=GREY, bgcolor=BLACK))
            return
        y = 28
        for name, meta in reversed(caps):
            txt = "%s  %dB  %dM  %s" % (
                name[7:19], meta.get("bytes", 0), int(meta.get("freq", 0)),
                meta.get("peak", "-"))
            self._rows.append(Button(
                wri_s, y, 2, height=30, width=300, text=txt,
                fgcolor=WHITE, bgcolor=DARKBLUE, textcolor=WHITE,
                callback=self._open, args=(name,)))
            y += 34

    def _open(self, button, name):
        Screen.change(CaptureScreen, args=(name,))


class CaptureScreen(Screen):
    """Detail view for one saved capture: decode + hex, with delete."""

    def __init__(self, name):
        super().__init__()
        self.name = name
        self._armed = False
        try:
            self.meta, self.data = subghz.load_capture(name)
        except Exception:
            self.meta, self.data = {}, b""

        Label(wri_s, 2, 2, "cap %s" % name[:26], fgcolor=CYAN, bgcolor=BLACK)
        m = self.meta
        Label(wri_s, 22, 2, "%.2f MHz  peak %s  %dB" %
              (m.get("freq", 0), m.get("peak"), m.get("bytes", len(self.data))),
              fgcolor=WHITE, bgcolor=BLACK)

        sym = self.meta.get("sym_us") or _sym_us()
        res = subghz.decode(self.data, sym)
        g = res["guess"]
        if g:
            Label(wri_s, 40, 2, "%s  %s  %d bits" %
                  (g["protocol"], g["hex"], g["bits"]),
                  fgcolor=GREEN, bgcolor=BLACK)
        elif res.get("noise"):
            Label(wri_s, 40, 2, "noisy/weak signal (no clean pulses)",
                  fgcolor=YELLOW, bgcolor=BLACK)
        else:
            Label(wri_s, 40, 2, "no protocol match (unit ~%d us)" %
                  int(res["unit_us"]), fgcolor=YELLOW, bgcolor=BLACK)
        Label(wri_s, 58, 2, "runs %d  edges %d  unit ~%d us" %
              (res["runs"], res["edges"], int(res["unit_us"])),
              fgcolor=WHITE, bgcolor=BLACK)

        Label(wri_s, 78, 2, "hex:", fgcolor=WHITE, bgcolor=BLACK)
        yy = 94
        for i in range(0, min(80, len(self.data)), 16):
            chunk = self.data[i:i + 16]
            Label(wri_s, yy, 2, "%04x " % i +
                  " ".join(["%02x" % b for b in chunk]),
                  fgcolor=WHITE, bgcolor=BLACK)
            yy += 12

        self.del_btn = Button(wri_s, 194, 2, height=34, width=150,
                              text="Delete", fgcolor=WHITE, bgcolor=RED,
                              textcolor=WHITE, callback=self._on_delete)
        CloseButton(wri)

    def _on_delete(self, button):
        # Two-tap confirm (no modal dialog): first tap arms, second deletes.
        if not self._armed:
            self._armed = True
            button.text = "Confirm delete?"
            button.draw = True
            return
        subghz.delete_capture(self.name)
        Screen.back()          # SavedScreen.after_open rebuilds the list

    def on_hide(self):
        self._armed = False
