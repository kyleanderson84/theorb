# cc1101.py — CC1101 sub-GHz radio driver (SPI) for The Orb.
#
# The CC1101 is an SPI transceiver (300–928 MHz); this driver covers 433/315/868
# MHz OOK/ASK for the Sub-GHz screen (RSSI sweep + raw RX).
#
# Wiring (module -> ESP32-S3), as used on this board:
#   SCK      -> GPIO2
#   MOSI(SI) -> GPIO14
#   MISO(SO) -> GPIO3
#   CSN      -> GPIO21
#   GDO0     -> GPIO15   (shared with touch/audio I2C SCL — kept tri-stated!)
#   GDO2     -> GPIO16   (shared with touch/audio I2C SDA — kept tri-stated!)
#   VCC 3V3, GND common.  MISO/GDO1 -> GPIO3.
#
# IMPORTANT: GDO0/GDO2 are wired onto the shared I2C bus (SCL=15/SDA=16). We
# program IOCFG0/IOCFG1/IOCFG2 = 0x2E (tri-state) so the radio never drives
# those lines while touch/audio use I2C. RX is done through the FIFO, not GDO.
#
# SPI quirk discovered on this hardware: single-byte reads of the status
# registers (0x30–0x3D) return garbage, but the same read with the burst bit
# set (0x40) returns correct data. Config registers (0x00–0x2F) read fine with
# a single access. This driver encodes that split in _read_config/_read_status.
#
# Usage:
#   from cc1101 import CC1101
#   radio = CC1101()
#   radio.present()                 # -> True if PARTNUM/VERSION look right
#   radio.config_ook(433.92)        # OOK RX profile
#   radio.rx(); ...; radio.rssi_dbm()
#   radio.idle()

import machine
import time

# SPI access bits
_WRITE = 0x00
_BURST = 0x40
_READ = 0x80

# Strobes / command registers
_SRES = 0x30
_SFSTXON = 0x31
_SXOFF = 0x32
_SCAL = 0x33
_SRX = 0x34
_STX = 0x35
_SIDLE = 0x36
_SFRX = 0x3A
_SFTX = 0x3B

# Config registers
_IOCFG2 = 0x00
_IOCFG1 = 0x01
_IOCFG0 = 0x02
_FIFOTHR = 0x03
_SYNC1 = 0x04
_SYNC0 = 0x05
_PKTCTRL1 = 0x07
_PKTCTRL0 = 0x08
_CHANNR = 0x0A
_FSCTRL1 = 0x0B
_FSCTRL0 = 0x0C
_FREQ2 = 0x0D
_FREQ1 = 0x0E
_FREQ0 = 0x0F
_MDMCFG4 = 0x10
_MDMCFG3 = 0x11
_MDMCFG2 = 0x12
_MDMCFG1 = 0x13
_MDMCFG0 = 0x14
_DEVIATN = 0x15
_MCSM2 = 0x16
_MCSM1 = 0x17
_MCSM0 = 0x18
_FOCCFG = 0x19
_BSCFG = 0x1A
_AGCCTRL2 = 0x1B
_AGCCTRL1 = 0x1C
_AGCCTRL0 = 0x1D
_FREND1 = 0x21
_FREND0 = 0x22
_FSCAL3 = 0x23
_FSCAL2 = 0x24
_FSCAL1 = 0x25
_FSCAL0 = 0x26
_FSTEST = 0x29
_TEST2 = 0x2C
_TEST1 = 0x2D
_TEST0 = 0x2E

# Status registers (read with the burst bit set on this hardware)
_PARTNUM = 0x30
_VERSION = 0x31
_RSSI = 0x34
_MARCSTATE = 0x35
_RXBYTES = 0x3B
_TXBYTES = 0x3A

_FIFO = 0x3F

# Status-byte state field (bits 6:4) -> name. NOTE: this enum differs from
# MARCSTATE's; the status byte is 0=IDLE 1=RX 2=TX 3=FSTXON 4=CAL 5=SETTLING
# 6=RXFIFO_OVERFLOW 7=TXFIFO_UNDERFLOW.
_STATUS_STATES = {
    0: "IDLE", 1: "RX", 2: "TX", 3: "FSTXON",
    4: "CALIBRATE", 5: "SETTLING", 6: "RXFIFO_OVERFLOW", 7: "TXFIFO_UNDERFLOW",
}

# MARCSTATE -> name
_STATES = {
    0x00: "SLEEP", 0x01: "IDLE", 0x02: "XOFF", 0x03: "VCOON_MC",
    0x04: "REGON_MC", 0x05: "MANCAL", 0x06: "VCOON", 0x07: "REGON",
    0x08: "STARTCAL", 0x09: "BWBOOST", 0x0A: "FS_LOCK", 0x0B: "IFADCON",
    0x0C: "ENDCAL", 0x0D: "RX", 0x0E: "RX_END", 0x0F: "RX_RST",
    0x10: "TXRX_SWITCH", 0x11: "RXFIFO_OVERFLOW", 0x12: "FSTXON",
    0x13: "TX", 0x14: "TX_END", 0x15: "RXTX_SWITCH", 0x16: "TXFIFO_UNDERFLOW",
}

# OOK/ASK raw-RX profile: OOK modulation, no sync/preamble, infinite FIFO so
# the demodulated bitstream streams into the RX FIFO for capture.
_OOK = {
    _IOCFG2: 0x2E, _IOCFG1: 0x2E, _IOCFG0: 0x2E,   # tri-state GDO (I2C shared)
    _FIFOTHR: 0x47,
    _PKTCTRL1: 0x00,                                # no append-status / addr check
    _PKTCTRL0: 0x02,                                # NORMAL fmt | LENGTH_INFINITE
    _FSCTRL1: 0x06,
    _MDMCFG4: 0x8B, _MDMCFG3: 0xF8,                 # ~4.8 kBaud, ~100 kHz RX BW
    _MDMCFG2: 0x30,                                 # ASK/OOK, no preamble/sync
    _MDMCFG1: 0x22, _MDMCFG0: 0xF8,
    _DEVIATN: 0x15,
    _MCSM2: 0x07, _MCSM1: 0x0C, _MCSM0: 0x18,       # RXOFF_MODE = stay in RX
    _FOCCFG: 0x16, _BSCFG: 0x6C,
    _AGCCTRL2: 0x03, _AGCCTRL1: 0x40, _AGCCTRL0: 0x91,
    _FREND1: 0x56, _FREND0: 0x10,
    _FSCAL3: 0xE9, _FSCAL2: 0x2A, _FSCAL1: 0x00, _FSCAL0: 0x1F,
}

_XTAL = 26_000_000


class CC1101:
    def __init__(self, cs=21, sck=2, mosi=14, miso=3, spi=None):
        if spi is not None:
            self.spi = spi
        else:
            self.spi = machine.SPI(
                2, baudrate=100_000, polarity=0, phase=0,
                sck=machine.Pin(sck), mosi=machine.Pin(mosi),
                miso=machine.Pin(miso),
            )
        self.cs = machine.Pin(cs, machine.Pin.OUT, value=1)
        self.version = None
        self.partnum = None

    # -- low level -----------------------------------------------------
    def _xfer(self, buf):
        rx = bytearray(len(buf))
        self.cs(0)
        self.spi.write_readinto(bytes(buf), rx)
        self.cs(1)
        return rx

    def _strobe(self, addr):
        self.cs(0)
        self.spi.write(bytes([addr]))
        self.cs(1)

    def _write(self, addr, val):
        self.cs(0)
        self.spi.write(bytes([_WRITE | addr, val]))
        self.cs(1)

    def _write_many(self, addr, values):
        self.cs(0)
        self.spi.write(bytes([_BURST | _WRITE | addr]) + bytes(values))
        self.cs(1)

    def _read_config(self, addr):
        # single access; data is byte 1, status byte is byte 0
        rx = self._xfer(bytes([_READ | addr, 0x00]))
        return rx[1], rx[0]

    def _read_status(self, addr):
        # burst bit required for correct status-register data on this hw
        rx = self._xfer(bytes([_BURST | _READ | addr, 0x00, 0x00]))
        return rx[1], rx[0]

    def _status_byte(self):
        # IMPORTANT: a *single* access to a status register forces the radio
        # back to IDLE, so the status byte is read via a burst access instead.
        return self._read_status(_MARCSTATE)[1]

    # -- identity ------------------------------------------------------
    def reset(self):
        self._strobe(_SRES)
        time.sleep_ms(5)

    def read_partnum(self):
        self.partnum = self._read_status(_PARTNUM)[0]
        return self.partnum

    def read_version(self):
        self.version = self._read_status(_VERSION)[0]
        return self.version

    def present(self):
        # A genuine CC1101 reports PARTNUM 0x00 and VERSION 0x04/0x14.
        return self.read_partnum() == 0x00 and self.read_version() in (0x04, 0x14)

    # -- configuration -------------------------------------------------
    def set_freq(self, mhz):
        # FREQ word = round(f_hz * 2^16 / f_xosc)
        word = int(round((mhz * 1_000_000) * 65536 / _XTAL))
        self._write(_FREQ2, (word >> 16) & 0xFF)
        self._write(_FREQ1, (word >> 8) & 0xFF)
        self._write(_FREQ0, word & 0xFF)
        return word

    def set_channel(self, ch):
        self._write(_CHANNR, ch & 0xFF)

    def datarate(self):
        # R = (256 + DRATE_M) * 2^DRATE_E / 2^28 * f_xosc   [baud]
        # DRATE_E = MDMCFG4[3:0], DRATE_M = MDMCFG3.
        e = self._read_config(_MDMCFG4)[0] & 0x0F
        m = self._read_config(_MDMCFG3)[0]
        return (256 + m) * (1 << e) / (1 << 28) * _XTAL

    def symbol_us(self):
        # One raw OOK bit in the RX FIFO = one symbol period. With the _OOK
        # profile this is ~10us, giving fine resolution for pulse-width decode.
        baud = self.datarate()
        return (1e6 / baud) if baud else 10.0

    def config_ook(self, mhz=433.92):
        self.reset()
        for reg in sorted(_OOK):
            self._write(reg, _OOK[reg])
        self.set_freq(mhz)
        self._strobe(_SIDLE)

    def set_ook(self):
        # apply the OOK modem profile without touching the frequency
        for reg in sorted(_OOK):
            self._write(reg, _OOK[reg])

    # -- state ---------------------------------------------------------
    def idle(self):
        self._strobe(_SIDLE)

    def rx(self):
        # SFRX/SRX only take effect cleanly from IDLE (SIDLE first).
        self._strobe(_SIDLE)
        self._strobe(_SFRX)
        self._strobe(_SRX)

    def tx(self):
        self._strobe(_STX)

    def status(self):
        marc, st = self._read_status(_MARCSTATE)
        rssi = self._read_status(_RSSI)[0]
        rxbytes = self._read_status(_RXBYTES)[0]
        return {
            "state": st >> 4,
            "state_name": _STATUS_STATES.get(st >> 4, "?"),
            "fifo_rx": st & 0x0F,
            "marcstate": marc,
            "marcstate_name": _STATES.get(marc, "?"),
            "rxbytes": rxbytes & 0x7F,
            "rssi_raw": rssi,
            "rssi_dbm": self._rssi_dbm(rssi),
        }

    @staticmethod
    def _rssi_dbm(dec):
        if dec >= 128:
            dec -= 256
        return round(dec / 2 - 74)

    def rssi(self):
        return self._read_status(_RSSI)[0]

    def rssi_dbm(self):
        return self._rssi_dbm(self.rssi())

    def marcstate(self):
        return self._read_status(_MARCSTATE)[0]

    def rx_bytes(self):
        return self._read_status(_RXBYTES)[0] & 0x7F

    def read_rx_fifo(self, n):
        if n <= 0:
            return b""
        # FIFO burst read; status byte then n data bytes
        rx = self._xfer(bytes([_BURST | _READ | _FIFO]) + bytes([0] * n))
        return bytes(rx[1:1 + n])

    # -- capture -------------------------------------------------------
    def _sweep(self, freqs, dwell_ms=40, settle_ms=6):
        best = (-999, None)
        out = []
        for f in freqs:
            self.set_freq(f)
            self.rx()
            time.sleep_ms(dwell_ms)
            dbm = self.rssi_dbm()
            out.append((f, dbm))
            if dbm > best[0]:
                best = (dbm, f)
            self.idle()
            if settle_ms:
                time.sleep_ms(settle_ms)
        return out, best

    def capture(self, duration_ms=2000, threshold_dbm=-90, max_bytes=256):
        """RSSI-gated raw OOK capture at the current frequency.

        Reads the RX FIFO only while the signal is above threshold (the OOK
        slicer idles at 0xFF, so a burst is gated on RSSI). Returns
        (bytes, peak_rssi_dbm).
        """
        self.rx()
        buf = bytearray()
        peak = -999
        above = False
        end = time.ticks_add(time.ticks_ms(), duration_ms)
        while time.ticks_diff(end, time.ticks_ms()) > 0:
            dbm = self.rssi_dbm()
            if dbm > peak:
                peak = dbm
            hot = dbm > threshold_dbm
            if hot and not above:
                n = self.rx_bytes()          # drop stale idle bytes
                if n:
                    self.read_rx_fifo(n)
                above = True
            if hot:
                n = self.rx_bytes()
                if n:
                    buf += self.read_rx_fifo(n)
                    if len(buf) >= max_bytes:
                        break
            elif above:
                above = False
        self.idle()
        return bytes(buf[:max_bytes]), peak


_radio = None


def open_radio():
    """Return a shared CC1101 instance.

    The SPI bus (SCK=2, MOSI=14, MISO=3, CS=21) is a singleton: the Sub-GHz
    screen and the agent payload both use this handle so only one SPI object
    is ever created for the radio.
    """
    global _radio
    if _radio is None:
        _radio = CC1101()
    return _radio

