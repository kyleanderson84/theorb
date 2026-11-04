# agent_payload.py — Hot-swappable payload (lives on the VFS, not in firmware).
#
# The remote agent rewrites this file and pushes it down. Keep it self-contained:
# it may import frozen drivers (cc1101, es8311_init, etc.) and stdlib only.
#
# Contract:
#   MODULE_NAME           short id shown in the UI
#   setup(ctx)            optional, once per load
#   run(ctx)              once per epoch (sync or async); may await
#   teardown(ctx)         optional, before unload
#
# ctx surface:
#   ctx.log(msg)          append to the rolling batch log
#   ctx.emit_status(str)  push a status line to the device screen
#   ctx.time_left_ms()    ms remaining in this epoch
#   ctx.state             dict that persists across epochs of this payload
#   ctx.hw                shared hardware handles (cc1101, ...)
#   ctx.net               network manager (None/offline-safe)

import time

MODULE_NAME = "subghz-scan"

# CC1101 default settings (tune from the cloud agent as needed).
FREQ_MHZ = 433.92
SWEEP = (315.0, 433.92, 868.0)


def setup(ctx):
    ctx.emit_status("payload: %s" % MODULE_NAME)
    ctx.log("payload setup %s freq=%s" % (MODULE_NAME, FREQ_MHZ))
    ctx.state["hits"] = 0


def run(ctx):
    # Collection epoch: sweep the sub-GHz bands and record RSSI peaks.
    radio = ctx.hw.get("cc1101") if ctx.hw else None
    if radio is None:
        try:
            import cc1101
            radio = cc1101.open_radio()
            ctx.hw["cc1101"] = radio
        except Exception as e:
            ctx.log("cc1101 unavailable: %r" % e)
            return

    if not radio.present():
        ctx.emit_status("no CC1101")
        ctx.log("cc1101 not detected")
        return

    radio.config_ook(FREQ_MHZ)
    ctx.emit_status("sub-GHz scan")
    samples = 0
    peak = (-999, None)
    while ctx.time_left_ms() > 0 and samples < 20:
        best_dbm, best_f = -999, None
        for f in SWEEP:
            radio.set_freq(f)
            radio.rx()
            time.sleep_ms(40)
            dbm = radio.rssi_dbm()
            if dbm > best_dbm:
                best_dbm, best_f = dbm, f
            radio.idle()
        samples += 1
        if best_dbm > peak[0]:
            peak = (best_dbm, best_f)
        ctx.state["hits"] = ctx.state.get("hits", 0) + 1
        if samples % 5 == 0:
            ctx.emit_status("scan %d/%d peak %d dBm" % (samples, 20, peak[0]))

    ctx.state["peak_dbm"] = peak[0]
    ctx.state["peak_freq"] = peak[1]
    ctx.log("epoch done: %d sweeps, peak %s dBm @ %s MHz" %
            (samples, peak[0], peak[1]))

    # Grab one raw OOK capture on the strongest band, decode, and persist it.
    if peak[1] is not None:
        radio.set_freq(peak[1])
        data, cap_peak = radio.capture(1500, threshold_dbm=-90)
        ctx.state["cap_bytes"] = len(data)
        ctx.state["cap_peak_dbm"] = cap_peak
        ctx.log("capture @ %s MHz: %d bytes, peak %d dBm" %
                (peak[1], len(data), cap_peak))
        try:
            import subghz
            res = subghz.decode(data, radio.symbol_us() or 10.0)
            g = res.get("guess")
            if g:
                ctx.state["cap_code"] = g["hex"]
                ctx.log("decoded %s %s (%d bits)" %
                        (g["protocol"], g["hex"], g["bits"]))
            else:
                ctx.log("no protocol match (%d edges)" % res["edges"])
            if res["edges"]:
                name = subghz.save_capture(data, peak[1], cap_peak,
                                           radio.symbol_us())
                ctx.state["cap_saved"] = name
                ctx.log("saved %s" % name)
        except Exception as e:
            ctx.log("decode/save failed: %r" % e)
