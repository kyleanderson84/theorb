# pn532.py — PN532 NFC reader driver (UART / HSU) for The Orb.
#
# This board has no on-board NFC; a PN532 breakout is wired to UART0, which
# is free because the MicroPython REPL/console runs on the native
# USB-Serial-JTAG peripheral (see board sdkconfig: CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG).
#
# Wiring (HSU mode — PN532 DIP switches set to HSU, 115200 8N1):
#   ESP TX  GPIO43 (U0TXD) -> PN532 RXD
#   ESP RX  GPIO44 (U0RXD) <- PN532 TXD
#   GND common, PN532 powered from 3V3.
#
# HSU frame format:
#   00 00 FF LEN LCS TFI <data...> DCS 00
#     LEN = number of bytes following LEN (TFI + data)
#     LCS = (~LEN + 1) & 0xFF          (so (LEN + LCS) & 0xFF == 0)
#     DCS = (~sum(TFI + data) + 1) & 0xFF  (so (sum(TFI..data) + DCS) & 0xFF == 0)
#     Host->PN532 TFI = 0xD4, PN532->host TFI = 0xD5
#   ACK frame: 00 00 FF 00 FF 00
#
# Usage:
#   from pn532 import PN532
#   nfc = PN532()              # defaults to UART0 GPIO43/44 @115200
#   nfc.begin()                # wake + SAMConfiguration (returns (ok, detail))
#   uid = nfc.read_uid(1000)   # bytes or None; nfc.last is a dict with metadata

import machine
import time

_HOST = 0xD4
_PN532 = 0xD5
_ACK = b"\x00\x00\xff\x00\xff\x00"
_WAKE = b"\x55\x55" + b"\x00" * 12

# Commands
_GET_FIRMWARE = 0x02
_RF_CONFIGURATION = 0x32
_SAM_CONFIGURATION = 0x14
_IN_LIST_PASSIVE_TARGET = 0x4A
_IN_RELEASE = 0x52

# InListPassiveTarget BrTy values
_BRTY_106A = 0x00  # ISO/IEC 14443-A (MIFARE / NTAG)
_BRTY_FELICA = 0x01
_BRTY_106B = 0x03

# SEL_RES (SAK) -> human label for the common 14443-A tags.
_SAK_NAMES = {
    0x00: "NTAG/Ultralight (UID 4)",
    0x08: "MIFARE Classic 1K",
    0x09: "MIFARE Classic Mini",
    0x18: "MIFARE Classic 4K",
    0x10: "MIFARE Plus / DESFire",
    0x11: "MIFARE Plus",
    0x20: "ISO 14443-4 (DESFire/JavaCard)",
    0x28: "SmartMX (JCOP)",
    0x40: "MIFARE Ultralight C",
    0x44: "ISO 14443-2 (UID 7)",
}


class PN532_I2C:
    """PN532 in I2C mode on the shared system bus (SDA=16, SCL=15).

    This matches the board's Bruce default (rfidModule = PN532_I2C_MODULE):
    PWR + GND, then module SDA->GPIO16 and SCL->GPIO15. Address 0x24.
    """

    ADDR = 0x24

    def __init__(self, i2c=None, scl=15, sda=16, freq=400000):
        if i2c is not None:
            self.i2c = i2c
        else:
            self.i2c = machine.I2C(0, scl=machine.Pin(scl),
                                   sda=machine.Pin(sda), freq=freq)
        self.firmware = None
        self.last = None

    def _write(self, frame):
        self.i2c.writeto(self.ADDR, frame)

    def _ready(self, timeout_ms):
        end = time.ticks_add(time.ticks_ms(), timeout_ms)
        while time.ticks_diff(end, time.ticks_ms()) > 0:
            try:
                if self.i2c.readfrom(self.ADDR, 1)[0] == 0x01:
                    return True
            except Exception:
                pass
            time.sleep_ms(5)
        return False

    def _read_frame(self, timeout_ms, maxlen=48):
        if not self._ready(timeout_ms):
            return None
        try:
            buf = self.i2c.readfrom(self.ADDR, maxlen)
        except Exception:
            return None
        return self._parse(bytes(buf[1:]))          # buf[0] is the status byte

    @staticmethod
    def _parse(b):
        i = b.find(b"\x00\x00\xff")
        if i < 0 or i + 5 > len(b):
            return None
        length = b[i + 3]
        lcs = b[i + 4]
        if (length + lcs) & 0xFF:
            return None
        data = b[i + 5:i + 5 + length]
        if len(data) < length or i + 5 + length >= len(b):
            return None
        dcs = b[i + 5 + length]
        if (sum(data) + dcs) & 0xFF:
            return None
        if length == 0:
            return b""                              # ACK
        if data[0] != _PN532:
            return None
        return bytes(data[1:])

    def call_function(self, cmd, params=b"", timeout_ms=1000):
        self._write(_build_frame(cmd, params))
        end = time.ticks_add(time.ticks_ms(), timeout_ms)
        while time.ticks_diff(end, time.ticks_ms()) > 0:
            fr = self._read_frame(time.ticks_diff(end, time.ticks_ms()))
            if fr is None or fr == b"":
                continue
            if fr[0] == (cmd + 1):
                return fr[1:]
        return None

    def begin(self, retries=3):
        for _ in range(retries):
            v = self.get_firmware_version()
            if v:
                self.firmware = v
                sam = self.call_function(_SAM_CONFIGURATION,
                                         bytes([0x01, 0x14, 0x01]))
                return sam is not None, "IC 0x%02x ver %d.%d" % (v[0], v[1], v[2])
        return False, "no response on I2C 0x24 (mode/wiring?)"

    def get_firmware_version(self):
        return self.call_function(_GET_FIRMWARE, timeout_ms=400)

    def read_uid(self, timeout_ms=1000, baud=_BRTY_106A):
        resp = self.call_function(_IN_LIST_PASSIVE_TARGET,
                                  bytes([0x01, baud]), timeout_ms=timeout_ms)
        if not resp or len(resp) < 6 or resp[0] != 0x01:
            return None
        atqa = (resp[3] << 8) | resp[2]
        sak = resp[4]
        idlen = resp[5]
        uid = bytes(resp[6:6 + idlen])
        if len(uid) != idlen:
            return None
        self.last = {"uid": uid, "atqa": atqa, "sak": sak,
                     "type": _SAK_NAMES.get(sak, "ISO14443-A (SAK 0x%02x)" % sak),
                     "baud": baud}
        return uid

    def release(self):
        try:
            self.call_function(_IN_RELEASE, bytes([0x00]), timeout_ms=200)
        except Exception:
            pass

    @staticmethod
    def uid_str(uid):
        return ":".join("%02X" % b for b in uid) if uid else "-"


def _build_frame(cmd, params=b""):
    body = bytes([cmd]) + bytes(params)
    length = len(body) + 1
    lcs = (-length) & 0xFF
    dcs = (-_HOST - sum(body)) & 0xFF
    return bytes([0x00, 0x00, 0xFF, length, lcs, _HOST]) + body + bytes([dcs, 0x00])


def _parse_frames(buf, tfi=_PN532):
    """Extract response payloads (TFI stripped) from a raw HSU byte buffer.

    ACKs yield b"". Garbage and partial trailing frames are ignored.
    """
    out = []
    i = 0
    n = len(buf)
    while True:
        j = buf.find(b"\x00\x00\xff", i)
        if j < 0 or j + 6 > n:
            break
        length = buf[j + 3]
        lcs = buf[j + 4]
        if length == 0x00 and lcs == 0xFF:          # ACK: 00 00 FF 00 FF 00
            out.append(b"")
            i = j + 6
            continue
        if (length + lcs) & 0xFF:                   # bad header, resync
            i = j + 3
            continue
        dcs_i = j + 5 + length
        if dcs_i + 2 > n:                           # incomplete frame
            break
        data = buf[j + 5:dcs_i]
        if not data or data[0] != tfi or buf[dcs_i + 1] != 0x00 \
                or (sum(data) + buf[dcs_i]) & 0xFF:
            i = j + 3
            continue
        out.append(bytes(data[1:]))
        i = dcs_i + 2
    return out


def open_reader():
    """Return the PN532 reader (UART0 / GPIO43-44).

    The board's I2C bus is shared with the touch panel and the audio codec, so
    we do not scan it from here.
    """
    return PN532()


class PN532:
    def __init__(self, tx=43, rx=44, baudrate=115200, uart=None):
        if uart is not None:
            self.uart = uart
        else:
            self.uart = machine.UART(
                0, baudrate=baudrate, tx=machine.Pin(tx), rx=machine.Pin(rx),
                timeout=200, rxbuf=256,
            )
        self.firmware = None      # (ic, ver, rev, support)
        self.last = None          # dict describing the most recent tag
        self._awake = False

    # ---- low level -------------------------------------------------------
    def _encode(self, data):
        body = bytes(data)
        length = len(body) + 1                      # +1 for TFI
        lcs = (-length) & 0xFF
        dcs = (-_HOST - sum(body)) & 0xFF
        return (bytes([0x00, 0x00, 0xFF, length, lcs, _HOST]) + body
                + bytes([dcs, 0x00]))

    def _send_ack(self):
        self.uart.write(_ACK)

    def call_function(self, cmd, params=b"", timeout_ms=1000, retries=3):
        """Send a command and return the response payload, or None.

        Each attempt is prefixed with the HSU wakeup (a cold chip can drop
        the first frame), then polls continuously for up to ~400ms because RF
        commands such as InListPassiveTarget take a while to answer.
        """
        frame = self._encode(bytes([cmd]) + bytes(params))
        end = time.ticks_add(time.ticks_ms(), timeout_ms)
        for _ in range(retries):
            if time.ticks_diff(end, time.ticks_ms()) <= 0:
                break
            self.uart.read()                        # drop stale bytes
            self.uart.write(_WAKE)
            self.uart.write(frame)
            window = time.ticks_add(time.ticks_ms(), 400)
            buf = b""
            while time.ticks_diff(window, time.ticks_ms()) > 0 \
                    and time.ticks_diff(end, time.ticks_ms()) > 0:
                d = self.uart.read()
                if d:
                    buf += d
                    for payload in _parse_frames(buf):
                        if payload and payload[0] == (cmd + 1):
                            self._send_ack()
                            return payload[1:]
                else:
                    time.sleep_ms(10)
        return None

    # ---- setup -----------------------------------------------------------
    def begin(self, retries=3):
        """Configure the PN532. Returns (ok, detail)."""
        for _ in range(retries):
            v = self.get_firmware_version()
            if v:
                self.firmware = v
                sam = self.call_function(_SAM_CONFIGURATION,
                                         bytes([0x01, 0x14, 0x01]))
                self._awake = sam is not None
                return self._awake, "IC 0x%02x ver %d.%d" % (v[0], v[1], v[2])
        return False, "no response (check HSU mode, wiring, power)"

    def wakeup(self):
        """Send the HSU wakeup sequence (0x55 0x55 then idle bytes)."""
        self.uart.write(_WAKE)
        time.sleep_ms(20)
        self.uart.read()
        self._awake = True

    def get_firmware_version(self):
        return self.call_function(_GET_FIRMWARE, timeout_ms=400)

    # ---- tag reading -----------------------------------------------------
    def _list_passive(self, baud, timeout_ms):
        return self.call_function(
            _IN_LIST_PASSIVE_TARGET, bytes([0x01, baud]), timeout_ms=timeout_ms
        )

    def parse_inlist(self, resp):
        """InListPassiveTarget response body (cmd byte stripped) -> UID or None.

        Fills self.last on success.
        """
        if not resp or resp[0] != 0x01 or len(resp) < 6:
            return None
        atqa = (resp[3] << 8) | resp[2]
        sak = resp[4]
        idlen = resp[5]
        uid = bytes(resp[6:6 + idlen])
        if len(uid) != idlen:
            return None
        self.last = {
            "uid": uid,
            "atqa": atqa,
            "sak": sak,
            "type": _SAK_NAMES.get(sak, "ISO14443-A (SAK 0x%02x)" % sak),
            "baud": _BRTY_106A,
        }
        return uid

    def read_uid(self, timeout_ms=1000, baud=_BRTY_106A):
        """Blocking poll for one ISO14443-A tag. Returns UID bytes or None."""
        return self.parse_inlist(self._list_passive(baud, timeout_ms) or b"")

    # ---- cooperative (async-friendly) polling ---------------------------
    def send_command(self, cmd, params=b""):
        """Queue a command without waiting (drains stale bytes first)."""
        self.uart.read(self.uart.any())
        self.uart.write(_WAKE)
        self.uart.write(self._encode(bytes([cmd]) + bytes(params)))

    def poll_frames(self):
        """Return complete response payloads buffered since the last call."""
        n = self.uart.any()
        if not n:
            return []
        return _parse_frames(self.uart.read(n))

    def begin_list_passive(self, baud=_BRTY_106A):
        self.send_command(_IN_LIST_PASSIVE_TARGET, bytes([0x01, baud]))

    def parse_passive(self, payload):
        """payload from poll_frames() -> UID bytes or None."""
        if not payload or payload[0] != (_IN_LIST_PASSIVE_TARGET + 1):
            return None
        return self.parse_inlist(payload[1:])

    def ack(self):
        self._send_ack()

    def release(self):
        try:
            self.call_function(_IN_RELEASE, bytes([0x00]), timeout_ms=200)
        except Exception:
            pass

    # ---- helpers ---------------------------------------------------------
    @staticmethod
    def uid_str(uid):
        return ":".join("%02X" % b for b in uid) if uid else "-"
