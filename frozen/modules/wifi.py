# wifi.py — WiFi scan/connect + trusted network storage for The Orb.
#
# Trusted networks are stored in config/known_nets.json as {ssid: password}.
# The agentic supervisor (agent/net.py) reads the same file for its cascade.

import network
import time
import ujson
import os

# Internal-flash fallback location.
KNOWN = "config/known_nets.json"
# SD card storage (SDIO mode: CLK=38, CMD=40, D0=39) so passwords survive
# a ROM flash. If no card is present we fall back to internal flash.
SD_MOUNT = "/sd"
SD_KNOWN = "/sd/known_nets.json"
_sta = None
_sd_ready = False


def _wlan():
    global _sta
    if _sta is None:
        _sta = network.WLAN(network.STA_IF)
    return _sta


_sd_obj = None  # MUST hold a reference or GC unmounts the card


def _sd_mounted():
    # os.listdir("/") yields names WITHOUT leading slash, e.g. "sd".
    try:
        return "sd" in os.listdir("/")
    except Exception:
        return False


def _mount_sd():
    """Mount the card (fresh SDCard object). Returns True on success."""
    global _sd_obj
    try:
        import machine
        sd = machine.SDCard(slot=1, sck=38, cmd=40, data=(39,))
        try:
            os.mount(sd, SD_MOUNT)
        except Exception:
            # Already mounted or mount failed; verify below.
            pass
        _sd_obj = sd  # keep it alive
        return _sd_mounted()
    except Exception:
        return False


def _commit_sd():
    """Force FAT writes to the physical card: unmount, then remount.

    Writes to the card only reach physical storage on unmount, so we
    always unmount+remount after a write to make it survive a reboot.
    """
    global _sd_ready
    try:
        if _sd_mounted():
            try:
                os.umount(SD_MOUNT)
            except Exception:
                pass
    except Exception:
        pass
    _sd_ready = False
    return _mount_sd()


def _ensure_sd():
    """Mount the SD card once if present. Returns True if /sd is usable."""
    global _sd_ready
    if _sd_mounted():
        _sd_ready = True
        return True
    if _mount_sd():
        _sd_ready = True
        return True
    _sd_ready = False
    return False


def known_path():
    """Return the active known-nets file path (SD preferred)."""
    if _ensure_sd():
        try:
            # Confirm we can actually write to the card.
            with open(SD_KNOWN, "a") as f:
                pass
            return SD_KNOWN
        except Exception:
            pass
    return KNOWN


def _migrate_if_needed():
    """On first SD use, copy internal-flash creds to the card so nothing is lost."""
    if not _ensure_sd():
        return
    try:
        if "known_nets.json" not in os.listdir(SD_MOUNT):
            try:
                with open(KNOWN) as f:
                    d = ujson.load(f)
                if d:
                    with open(SD_KNOWN, "w") as f:
                        ujson.dump(d, f)
                    _commit_sd()
            except Exception:
                pass
    except Exception:
        pass


def load_known():
    _migrate_if_needed()
    path = known_path()
    try:
        with open(path) as f:
            return ujson.load(f)
    except Exception:
        # If SD path failed, try internal fallback.
        if path != KNOWN:
            try:
                with open(KNOWN) as f:
                    return ujson.load(f)
            except Exception:
                pass
        return {}


def _sync_write(path, d):
    """Write JSON, commit to physical storage, and verify."""
    try:
        with open(path, "w") as f:
            ujson.dump(d, f)
            try:
                f.flush()
            except Exception:
                pass
        try:
            os.sync()
        except Exception:
            pass
        return True
    except Exception:
        return False


def save_known(d):
    path = known_path()
    if _sync_write(path, d):
        # Commit FAT to the card so it survives a reboot.
        _commit_sd()
        # Verify it actually landed after the remount.
        try:
            with open(path) as f:
                if ujson.load(f) == d:
                    return
        except Exception:
            pass
    # Fallback to internal flash if SD write failed.
    _sync_write(KNOWN, d)


def add_known(ssid, pw):
    d = load_known()
    d[ssid] = pw
    save_known(d)


def remove_known(ssid):
    d = load_known()
    if ssid in d:
        del d[ssid]
        save_known(d)


def is_known(ssid):
    return ssid in load_known()


def scan():
    """Return list of (ssid, rssi, authmode, is_known), strongest first.
    Authmode 0 = open. Hidden SSIDs (empty name) are skipped."""
    sta = _wlan()
    sta.active(True)
    known = load_known()
    out = []
    try:
        results = sta.scan()
    except Exception:
        return out
    seen = set()
    for r in results:
        try:
            name = r[0].decode() if isinstance(r[0], bytes) else r[0]
        except Exception:
            continue
        if not name or name in seen:
            continue
        seen.add(name)
        out.append((name, r[3], r[4], name in known))
    out.sort(key=lambda x: x[1], reverse=True)
    return out


def is_connected():
    return _wlan().isconnected()


def current_ssid():
    sta = _wlan()
    if sta.isconnected():
        try:
            return sta.config("ssid")
        except Exception:
            return "?"
    return None


def ip():
    sta = _wlan()
    if sta.isconnected():
        try:
            return sta.ifconfig()[0]
        except Exception:
            pass
    return None


def connect(ssid, pw="", timeout=12, save=True):
    """Connect to ssid. Returns (ok, message). Saves to known on success if save."""
    sta = _wlan()
    sta.active(True)
    try:
        sta.disconnect()
    except Exception:
        pass
    try:
        sta.connect(ssid, pw)
    except Exception as e:
        return False, "connect err: %s" % e
    t0 = time.time()
    while not sta.isconnected():
        if time.time() - t0 > timeout:
            return False, "timeout"
        time.sleep_ms(200)
    if save:
        add_known(ssid, pw)
    try:
        return True, sta.ifconfig()[0]
    except Exception:
        return True, "connected"


async def aconnect(ssid, pw="", timeout=12, save=True, on_status=None):
    """Async connect that yields to the event loop (keeps the GUI responsive).
    on_status(phase, detail) is called with 'start'/'ok'/'fail' as it progresses.
    Returns (ok, message)."""
    import asyncio
    sta = _wlan()
    sta.active(True)
    try:
        sta.disconnect()
    except Exception:
        pass
    if on_status:
        on_status("start", ssid)
    try:
        sta.connect(ssid, pw)
    except Exception as e:
        if on_status:
            on_status("fail", "connect err")
        return False, "connect err: %s" % e
    t0 = time.time()
    while not sta.isconnected():
        if time.time() - t0 > timeout:
            if on_status:
                on_status("fail", "timeout")
            return False, "timeout"
        await asyncio.sleep_ms(200)
    if save:
        add_known(ssid, pw)
    try:
        ip = sta.ifconfig()[0]
    except Exception:
        ip = "connected"
    if on_status:
        on_status("ok", ip)
    return True, ip


def disconnect():
    try:
        _wlan().disconnect()
    except Exception:
        pass
