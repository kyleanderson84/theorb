# LVGL <-> ili9341 display glue for ESP32-S3 (theorb)
# Registers the frozen ili9341 driver as an LVGL display device.
#
# Usage:
#   import lvgl_display
#   lvgl_display.init()
#   lv.timer_handler()  # (or via lv.timer via lvgl_display.tick())
import lvgl as lv
from ili9341 import Display

WIDTH = 320
HEIGHT = 240
PARTIAL_LINES = 40  # render buffer height

_disp = None
_drv = None


def _flush_cb(display, area, px_map):
    # LVGL gives us a rendered sub-region (area) and its RGB565 bytes.
    # The frozen ili9341 driver exposes _set_window + _wdata.
    x1, y1, x2, y2 = area
    _drv._set_window(x1, y1, x2, y2)
    _drv._wdata(px_map)
    if lv.display_flush_is_last(display):
        pass
    lv.display_flush_ready(display)


def init():
    global _disp, _drv
    if _disp is not None:
        return _disp
    _drv = Display()
    _disp = lv.display_create(WIDTH, HEIGHT)
    lv.display_set_color_format(_disp, lv.COLOR_FORMAT.RGB565)
    lv.display_set_resolution(_disp, WIDTH, HEIGHT)
    buf_size = WIDTH * PARTIAL_LINES * 2  # RGB565
    buf1 = bytearray(buf_size)
    buf2 = bytearray(buf_size)
    lv.display_set_buffers(_disp, buf1, buf2, buf_size, lv.RENDER_MODE.PARTIAL)
    lv.display_set_flush_cb(_disp, _flush_cb)
    return _disp


def tick():
    lv.timer_handler()


def deinit():
    global _disp, _drv
    if _disp is not None:
        lv.display_delete(_disp)
        _disp = None
    _drv = None
