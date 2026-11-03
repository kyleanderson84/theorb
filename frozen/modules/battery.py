# battery.py — Battery voltage/percent from GPIO9 (ADC1 ch8, x2 divider).
# ES3C28P: 2500mV = 0%, 4200mV = 100%. Uses read_uv() for calibrated millivolts.

from machine import ADC, Pin

MIN_MV = 2500
MAX_MV = 4200
# Heuristic: no charge-status pin on ES3C28P. Treat >= this as "on charger".
CHARGE_HINT_MV = 4150

_adc = None


def _get_adc():
    global _adc
    if _adc is None:
        _adc = ADC(Pin(9))
        try:
            _adc.atten(ADC.ATTN_11DB)  # 0..3.3V range
        except Exception:
            pass
    return _adc


def read_mv(samples=8):
    """Battery voltage in millivolts (averaged), with x2 divider applied."""
    adc = _get_adc()
    total = 0
    for _ in range(samples):
        total += adc.read_uv()
    pin_mv = total // samples // 1000
    return pin_mv * 2


def percent(mv=None):
    if mv is None:
        mv = read_mv()
    p = int(((mv - MIN_MV) / (MAX_MV - MIN_MV)) * 100)
    return max(0, min(100, p))


def status_str(mv=None):
    """Fixed-width status: '<pct>% <V>V' or 'CHG <pct>%' when charging."""
    if mv is None:
        mv = read_mv()
    p = percent(mv)
    if mv >= CHARGE_HINT_MV:
        s = "CHG %d%%" % p
    else:
        s = "%d%% %d.%02dV" % (p, mv // 1000, (mv % 1000) // 10)
    return s


def fixed_status(mv=None, width=12):
    """Status padded with spaces to `width` so a Label redraws a fixed area
    (avoids stale pixels when the text length changes)."""
    s = status_str(mv)
    if len(s) < width:
        s = s + " " * (width - len(s))
    return s
