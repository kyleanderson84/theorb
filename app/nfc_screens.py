# nfc_screens.py — NFC (PN532) reader screen.
# Flow: Launcher -> NFC -> tap a 13.56MHz tag -> show its UID + type.
#
# The PN532 is an external module on UART0 (GPIO43/44), which is free here
# because the REPL runs on the native USB-Serial-JTAG. See frozen/modules/pn532.py.

import asyncio
import time
from gui.core.tgui import Screen, ssd
from gui.core.writer import CWriter
from gui.widgets import CloseButton, Label, Button
import gui.fonts.freesans20 as font
import gui.fonts.font10 as small
from gui.core.colors import (BLACK, GREEN, BLUE, WHITE, RED, YELLOW, CYAN,
                             DARKBLUE, GREY)

wri = CWriter(ssd, font, GREEN, BLACK, verbose=False)
wri_s = CWriter(ssd, small, WHITE, BLACK, verbose=False)


class NFCScreen(Screen):
    """Continuously poll for ISO14443-A tags and display the last UID."""

    def __init__(self):
        super().__init__()
        Label(wri, 2, 2, "NFC", fgcolor=CYAN, bgcolor=BLACK)
        self.status = Label(wri_s, 26, 2, "", fgcolor=YELLOW, bgcolor=BLACK)
        self.uid = Label(wri, 70, 2, "no tag", fgcolor=GREEN, bgcolor=BLACK)
        self.detail = Label(wri_s, 100, 2, "", fgcolor=WHITE, bgcolor=BLACK)
        self.detail2 = Label(wri_s, 120, 2, "", fgcolor=GREY, bgcolor=BLACK)

        self._scanning = True
        self._reader = None
        self._busy = False
        self.btn = Button(wri, 150, 2, height=30, width=120, text="Rescan",
                          fgcolor=WHITE, bgcolor=DARKBLUE, textcolor=WHITE,
                          callback=self._rescan)
        Label(wri_s, 150, 140, "tap a tag (13.56MHz)", fgcolor=GREY,
              bgcolor=BLACK)
        CloseButton(wri)
        self.reg_task(self._scan_loop(), on_change=True)

    async def _scan_loop(self):
        import pn532
        if self._reader is None:
            self._reader = pn532.open_reader()
        self.status.value("init reader...")
        ok, detail = self._reader.begin()
        if not ok:
            self.status.value("no reader: " + str(detail)[:26])
            self.uid.value("-")
            self.detail.value("PN532 on UART0 GPIO43/44")
            self.detail2.value("check HSU mode + power")
            return
        self.status.value("tap a tag...")
        last = None
        while self._scanning:
            self._reader.begin_list_passive()
            uid = None
            deadline = time.ticks_add(time.ticks_ms(), 250)
            while time.ticks_diff(deadline, time.ticks_ms()) > 0:
                await asyncio.sleep_ms(15)
                for payload in self._reader.poll_frames():
                    u = self._reader.parse_passive(payload)
                    if u is not None:
                        self._reader.ack()
                        uid = u
                if uid is not None:
                    break
            if uid is not None:
                if uid != last:
                    last = uid
                    self._show(uid, self._reader.last)
            elif last is not None:
                last = None
                self.uid.value("no tag")
                self.detail.value("")
                self.detail2.value("")
                self.status.value("tap a tag...")

    def _show(self, uid, meta):
        self.uid.value(pn532_uid(uid))
        self.detail.value(meta.get("type", "ISO14443-A")[:36])
        self.detail2.value("ATQA %04X  SAK %02X  %d bytes" %
                           (meta.get("atqa", 0), meta.get("sak", 0),
                            len(uid)))
        self.status.value("tag detected")

    def _rescan(self, button):
        self.uid.value("no tag")
        self.detail.value("")
        self.detail2.value("")
        self.status.value("tap a tag...")

    def on_hide(self):
        self._scanning = False
        try:
            if self._reader:
                self._reader.release()
        except Exception:
            pass


def pn532_uid(uid):
    return ":".join("%02X" % b for b in uid)
