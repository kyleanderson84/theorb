# LVGL display test for ESP32-S3 (theorb project)
# Uses lv_binding_micropython's hybrid ili9341 driver.
#
# Board pins (from project map):
#   SCK  = 14   (clk)
#   MOSI = 3    (mosi)
#   CS   = 10   (cs)
#   DC   = 46   (dc)
#   BL   = 45   (backlight)
#
# Display: 320x240 (landscape), rotated, inversion ON.

import lvgl as lv
import espidf as esp
from ili9XXX import ili9341

# ---- Display driver init ----
disp = ili9341(
    miso=-1,          # write-only SPI, no MISO needed
    mosi=3,
    clk=14,
    cs=10,
    dc=46,
    rst=-1,           # no explicit reset pin wired
    power=-1,
    backlight=45,
    backlight_on=1,   # active-high backlight
    spihost=esp.HSPI_HOST,  # adjust if needed
    mhz=40,
    width=320,
    height=240,
    invert=True,
    double_buffer=True,
    color_format=lv.COLOR_FORMAT.RGB565,
)

# ---- Simple LVGL UI ----
scr = lv.screen_active()
scr.set_style_bg_color(lv.color_hex(0x000000), 0)

label = lv.label(scr)
label.set_text("Hello World")
label.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
label.center()

# A green button just below center
btn = lv.button(scr)
btn.set_size(120, 50)
btn.align(lv.ALIGN.CENTER, 0, 40)
btn.set_style_bg_color(lv.color_hex(0x00C853), 0)
btn_label = lv.label(btn)
btn_label.set_text("CLICK")
btn_label.center()

print("LVGL_UI_OK")
