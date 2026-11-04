# subghz.py — OOK pulse analysis and capture storage for the Sub-GHz screen.
#
# The CC1101 raw/OOK profile streams the demodulated slicer output into the RX
# FIFO one bit per symbol period (see cc1101.symbol_us(); ~10 us with the stock
# profile, i.e. fine temporal resolution). Here we turn that bitstream into
# run-length pulse widths, make a best-effort decode of the common tri-bit
# remotes (EV1527 / PT2262), and persist raw captures under /captures.
#
# NOTE: analysis only — RF "replay" via the CC1101 is not wired on this board.
# OOK TX needs GDO0, which shares the touch/audio I2C SCL line (GPIO15), so the
# radio keeps its GDO pins tri-stated and we never transmit.

import os
import json
import time

DIR = "captures"
_MAGIC = "ORBCAP1"


# ---- bitstream analysis ---------------------------------------------
def analyse(data):
    """Return (total_bits, transitions) for a raw OOK byte buffer."""
    bits = len(data) * 8
    trans = 0
    prev = None
    for b in data:
        for i in range(7, -1, -1):
            bit = (b >> i) & 1
            if prev is not None and bit != prev:
                trans += 1
            prev = bit
    return bits, trans


def rle(data):
    """Run-length encode a byte stream (MSB first) -> [(bit, count), ...]."""
    runs = []
    prev = None
    for b in data:
        for i in range(7, -1, -1):
            bit = (b >> i) & 1
            if bit == prev:
                runs[-1][1] += 1
            else:
                runs.append([bit, 1])
                prev = bit
    return runs


def _denoise(runs, min_run=2):
    """Merge runs shorter than `min_run` (slicer glitches) into neighbours.

    At the stock ~100 kBaud OOK profile (~10 us/sample) real pulses are tens of
    samples long, but a weak/noisy signal produces many 1-sample toggles. Left
    alone those dominate the histogram and the unit estimate collapses to 1.
    """
    out = [[b, c] for b, c in runs]
    changed = True
    while changed:
        changed = False
        for i in range(len(out)):
            if out[i][1] < min_run:
                if i > 0:
                    out[i - 1][1] += out[i][1]
                elif len(out) > 1:
                    out[i + 1][1] += out[i][1]
                else:
                    break
                del out[i]
                merged = []
                for b, c in out:
                    if merged and merged[-1][0] == b:
                        merged[-1][1] += c
                    else:
                        merged.append([b, c])
                out = merged
                changed = True
                break
    return out


def _unit_samples(runs):
    """Estimate the base pulse unit (in samples).

    The unit is the smallest run length that recurs often. Requiring >=3 hits
    before falling back to >=2 rejects 1-2 sample slicer glitches, which would
    otherwise be mistaken for the unit and break the width classification.
    """
    hist = {}
    for _, c in runs:
        hist[c] = hist.get(c, 0) + 1
    if not hist:
        return 1
    for need in (3, 2):
        for v in sorted(hist):
            if hist[v] >= need:
                return v
    return min(hist)


def _invert(runs):
    return [[1 - b, c] for b, c in runs]


def _sym(v, u):
    # Classify a pulse width as 1 or 3 units (or 99 = neither).
    if v < 2 * u:
        return 1
    if v < 6 * u:
        return 3
    return 99


def decode_tribit(runs, sym_us, max_bits=64):
    """Best-effort EV1527/PT2262 tri-bit decode. Returns dict or None.

    A frame is: sync (short high + long low) then N (high,low) pairs, where
    bit 0 = 1u high + 3u low and bit 1 = 3u high + 1u low.
    """
    runs = _denoise(runs)
    n = len(runs)
    if n < 8:
        return None
    u = _unit_samples(runs)
    if u < 1:
        return None

    # Find a sync: a low run far longer than the unit.
    sync = None
    for i in range(n):
        b, c = runs[i]
        if b == 0 and c >= 8 * u:
            sync = i
            break
    if sync is None:
        return None

    bits = []
    i = sync + 1
    while i + 1 < n and len(bits) < max_bits:
        hb, hc = runs[i]
        lb, lc = runs[i + 1]
        if hb != 1 or lb != 0:
            break
        hs, ls = _sym(hc, u), _sym(lc, u)
        if hs == 1 and ls == 3:
            bits.append(0)
        elif hs == 3 and ls == 1:
            bits.append(1)
        else:
            break
        i += 2
    if len(bits) < 8:
        return None
    code = 0
    for b in bits:
        code = (code << 1) | b
    return {
        "protocol": "EV1527/PT2262",
        "bits": len(bits),
        "code": code,
        "hex": _hex(code, (len(bits) + 3) // 4),
        "unit_us": u * sym_us,
    }


def _hex(v, nibbles):
    s = "%X" % v
    return s if len(s) >= nibbles else "0" * (nibbles - len(s)) + s


def decode(data, sym_us=10.0):
    """Analyse a raw OOK capture. Returns a dict with pulses + a decode guess."""
    bits, edges = analyse(data)
    runs = _denoise(rle(data))
    unit_samples = _unit_samples(runs) if runs else 1
    out = {
        "bytes": len(data),
        "bits": bits,
        "edges": edges,
        "runs": len(runs),
        "noise": unit_samples <= 1 and edges > 0,
        "unit_us": unit_samples * sym_us,
        "guess": None,
    }
    if edges:
        # Try both slicer polarities (carrier may idle high or low).
        guess = decode_tribit(runs, sym_us)
        if guess is None:
            guess = decode_tribit(_invert(runs), sym_us)
            if guess is not None:
                guess["inverted"] = True
        out["guess"] = guess
    return out


def pulse_us(data, sym_us=10.0, limit=24):
    """First `limit` pulse widths in microseconds, as 'lvl:us' strings."""
    runs = rle(data)
    out = []
    for b, c in runs[:limit]:
        out.append("%d:%d" % (b, int(c * sym_us)))
    return out


# ---- capture storage -------------------------------------------------
def _ensure_dir():
    try:
        os.mkdir(DIR)
    except OSError:
        pass


def _path(name):
    return "%s/%s" % (DIR, name)


def save_capture(data, freq, peak=None, sym_us=None):
    """Persist a raw capture. Returns the stored filename."""
    _ensure_dir()
    meta = {
        "magic": _MAGIC,
        "freq": freq,
        "peak": peak,
        "bytes": len(data),
        "sym_us": sym_us,
        "ts": int(time.time()),
    }
    base = "subghz_%d_%d" % (int(freq * 100), int(time.ticks_ms()))
    name = base + ".cap"
    n = 1
    while _exists(_path(name)):           # never clobber an existing capture
        name = "%s_%d.cap" % (base, n)
        n += 1
    with open(_path(name), "wb") as f:
        f.write((json.dumps(meta) + "\n").encode())
        f.write(data)
    return name


def _exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False


def load_capture(name):
    """Return (meta_dict, raw_bytes) for a stored capture."""
    with open(_path(name), "rb") as f:
        raw = f.read()
    nl = raw.find(b"\n")
    meta = json.loads(raw[:nl].decode())
    return meta, raw[nl + 1:]


def list_captures():
    """Return [(name, meta_dict), ...] sorted by name (newest last)."""
    _ensure_dir()
    out = []
    try:
        names = os.listdir(DIR)
    except OSError:
        return out
    for name in sorted(names):
        if isinstance(name, bytes):
            name = name.decode()
        if not name.endswith(".cap"):
            continue
        try:
            meta, _ = load_capture(name)
        except Exception:
            continue
        out.append((name, meta))
    return out


def delete_capture(name):
    try:
        os.remove(_path(name))
        return True
    except OSError:
        return False
