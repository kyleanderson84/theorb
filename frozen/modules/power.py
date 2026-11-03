# power.py — Backlight brightness + deep-sleep power-off for ES3C28P.
#
# Backlight: GPIO45, driven by PWM. Brightness 0..100.
# Power off: deep sleep, wake on BOOT button (GPIO0, active LOW) — matches
# Bruce's powerOff(): backlight off, amp off, display sleep, ext0 wake.
#
# The display sleep + amp-off are done here too so power-off is clean.

import machine
from machine import Pin, PWM

BL_PIN = 45
AMP_EN_PIN = 1  # FM8002E amp enable, active LOW (HIGH = disabled/off)
BOOT_PIN = 0    # wake source, active LOW

_bl = None
_brightness = 100

# Store brightness persistently on the VFS so it survives reboots.
_CFG = "config/power.json"


def _load():
    global _brightness
    try:
        import ujson
        with open(_CFG) as f:
            _brightness = int(ujson.load(f).get("brightness", 100))
    except Exception:
        _brightness = 100


def _save():
    try:
        import ujson
        with open(_CFG, "w") as f:
            ujson.dump({"brightness": _brightness}, f)
    except Exception:
        pass


def _bl_pwm():
    global _bl
    if _bl is None:
        _bl = PWM(Pin(BL_PIN))
        _bl.freq(1000)
    return _bl


def set_brightness(pct, save=True):
    """Set backlight brightness 0..100 (%)."""
    global _brightness
    pct = max(0, min(100, int(pct)))
    _brightness = pct
    if pct == 0:
        # Fully off: hold pin low via plain output to avoid faint PWM glow.
        try:
            _bl_pwm().deinit()
        except Exception:
            pass
        Pin(BL_PIN, Pin.OUT, value=0)
    else:
        # duty_u16: 0..65535. Keep a small floor so low % still lights.
        duty = int(65535 * (0.15 + 0.85 * pct / 100))
        p = _bl_pwm()
        p.duty_u16(duty)
    if save:
        _save()
    return _brightness


def get_brightness():
    return _brightness


def init(save=False):
    """Load saved brightness and apply it."""
    _load()
    set_brightness(_brightness, save=save)


def power_off():
    """Turn off backlight + amp, sleep display, deep-sleep until BOOT pressed."""
    # Backlight off
    try:
        set_brightness(0, save=False)
    except Exception:
        Pin(BL_PIN, Pin.OUT, value=0)
    # Amp off (HIGH = disabled)
    try:
        Pin(AMP_EN_PIN, Pin.OUT, value=1)
    except Exception:
        pass
    # Display sleep (SLPIN 0x10) if the ssd object was registered.
    try:
        _ssd._wcmd(b"\x10")
    except Exception:
        pass
    # Wake on BOOT button (GPIO0) active low, then deep sleep.
    try:
        import esp32
        esp32.wake_on_ext0(pin=Pin(BOOT_PIN, Pin.IN, Pin.PULL_UP), level=0)
    except Exception:
        pass
    machine.deepsleep()


# Optional: register the display object so power_off can sleep it.
_ssd = None


def register_display(ssd):
    global _ssd
    _ssd = ssd
