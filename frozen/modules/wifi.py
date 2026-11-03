# wifi.py — WiFi scan/connect + trusted network storage for The Orb.
#
# Trusted networks are stored in config/known_nets.json as {ssid: password}.
# The agentic supervisor (agent/net.py) reads the same file for its cascade.

import network
import time
import ujson

KNOWN = "config/known_nets.json"
_sta = None


def _wlan():
    global _sta
    if _sta is None:
        _sta = network.WLAN(network.STA_IF)
    return _sta


def load_known():
    try:
        with open(KNOWN) as f:
            return ujson.load(f)
    except Exception:
        return {}


def save_known(d):
    try:
        with open(KNOWN, "w") as f:
            ujson.dump(d, f)
    except Exception:
        pass


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


def disconnect():
    try:
        _wlan().disconnect()
    except Exception:
        pass
