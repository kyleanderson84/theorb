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
    # Example collection epoch: report a heartbeat while time remains.
    # The real payload would sample the CC1101 driver via ctx.hw["cc1101"].
    start = time.ticks_ms()
    samples = 0
    while ctx.time_left_ms() > 0 and samples < 20:
        # Placeholder sampling tick - replace with radio reads.
        samples += 1
        ctx.state["hits"] = ctx.state.get("hits", 0) + 1
        time.sleep_ms(250)
        if samples % 5 == 0:
            ctx.emit_status("scan %d/%d" % (samples, 20))
    ctx.log("epoch done: %d samples, %d hits" % (samples, ctx.state["hits"]))
