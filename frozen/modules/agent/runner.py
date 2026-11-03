# agent/runner.py — Hot-swappable payload runner.
#
# The remote agent rewrites `agent_payload.py` on the VFS and pushes it down.
# This module loads and executes it against a stable interface, isolating the
# supervisor (frozen in flash) from the payload (on the filesystem).
#
# Payload contract — `agent_payload.py` must define:
#   MODULE_NAME = "subghz"            # short id, shown in UI
#   def run(ctx) -> None              # called once per epoch; may await
#
# Optional:
#   def setup(ctx) -> None            # called once on load/swap
#   def teardown(ctx) -> None         # called before unload
#
# `ctx` gives the payload a controlled surface — it never touches the supervisor
# directly, which keeps swaps safe and lets us stub hardware during testing.

import gc
import sys
import time


PAYLOAD_PATH = "agent_payload.py"
VALID_ARGS = ("ctx",)


class PayloadError(Exception):
    pass


class Payload:
    def __init__(self, path=PAYLOAD_PATH):
        self.path = path
        self.mod = None
        self.name = "idle"
        self.last_error = None

    def load(self, ctx):
        """Import the payload, validate it, run setup(). Returns True on success."""
        self._unload(quiet=True)
        try:
            if PAYLOAD_PATH in sys.modules:
                del sys.modules[PAYLOAD_PATH]
            self.mod = __import__(PAYLOAD_PATH.split(".")[0])
        except Exception as e:
            self.last_error = "load:%r" % e
            raise PayloadError(self.last_error)
        if not hasattr(self.mod, "run"):
            self.last_error = "no-run-fn"
            raise PayloadError(self.last_error)
        self.name = getattr(self.mod, "MODULE_NAME", "unnamed")
        setup = getattr(self.mod, "setup", None)
        if setup:
            try:
                _maybe_await(setup(ctx))
            except Exception as e:
                self.last_error = "setup:%r" % e
                raise PayloadError(self.last_error)
        return True

    def step(self, ctx):
        """Run one epoch. Returns error string or None.

        Async payloads (`async def run`) return a coroutine that the supervisor
        awaits via `astep`; sync payloads run here directly.
        """
        if self.mod is None:
            return "not-loaded"
        try:
            res = self.mod.run(ctx)
            if hasattr(res, "send"):  # coroutine -> caller must await
                return res
            return None
        except Exception as e:
            self.last_error = "run:%r" % e
            return self.last_error

    def _unload(self, quiet=False):
        if self.mod is None:
            return
        teardown = getattr(self.mod, "teardown", None)
        try:
            if teardown:
                teardown(None)
        except Exception:
            pass
        self.mod = None
        if PAYLOAD_PATH in sys.modules:
            del sys.modules[PAYLOAD_PATH]
        gc.collect()


class PayloadContext:
    """Controlled surface handed to the payload. Frozen supervisor owns all I/O."""

    def __init__(self, log, net, hw, deadline_ms):
        self.log = log            # callable(str) -> append to rolling log
        self.net = net            # agent.net.Net instance (or None if offline)
        self.hw = hw              # dict: 'cc1101', 'gui_status', etc.
        self.deadline_ms = deadline_ms
        self.state = {}           # payload scratch space, persists per swap

    def emit_status(self, text):
        cb = self.hw.get("gui_status")
        if cb:
            cb(text)

    def time_left_ms(self):
        return max(0, self.deadline_ms - time.ticks_ms())


def _maybe_await(res):
    # Deprecated: supervisor awaits coroutines itself. Kept for setup() which is
    # always expected to be synchronous; if it returns a coroutine we run it.
    if hasattr(res, "send"):
        try:
            import uasyncio as asyncio
        except ImportError:
            import asyncio
        asyncio.run(res)
    return res
