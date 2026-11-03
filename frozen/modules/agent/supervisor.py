# agent/supervisor.py — Static supervisor (frozen in firmware).
#
# This is the stable orchestrator that survives payload swaps. It owns:
#   - the epoch loop (collect -> check-in -> analyse -> re-arm)
#   - the network cascade and upstream sync
#   - payload hot-swap
#   - status broadcast to the GUI
#
# It is written as an async coroutine so it can be registered with the
# micropython-touch GUI (Screen.reg_task) and run alongside the UI without
# blocking touch handling or screen refresh.

import asyncio
import gc
import time
import ujson as json

from agent.net import Net
from agent.runner import Payload, PayloadContext

# Tunables (overridable via config/supervisor.json)
EPOCH_MS = const(15 * 60 * 1000)   # 15-minute collection epoch
SYNC_URL_DEFAULT = ""              # e.g. https://brain.example/ingest
STATUS_PATH = "status.json"
LOG_PATH = "logs/batch.log"


def _load_cfg():
    try:
        with open("config/supervisor.json") as f:
            return json.load(f)
    except Exception:
        return {}


class Supervisor:
    def __init__(self, gui_status=None, hw=None):
        cfg = _load_cfg()
        self.epoch_ms = cfg.get("epoch_ms", EPOCH_MS)
        self.sync_url = cfg.get("sync_url", SYNC_URL_DEFAULT)
        self.gui_status = gui_status
        self.hw = hw or {}
        if gui_status:
            self.hw["gui_status"] = gui_status
        self.net = Net(cfg.get("net_timeout", 8))
        self.payload = Payload()
        self.status = "init"
        self.epoch = 0
        self.running = False
        self.online = False
        self._ctx = None
        self._locked = False

    # ---- status broadcast ------------------------------------------------
    def _set_status(self, text):
        self.status = text
        if self.gui_status:
            try:
                self.gui_status(text)
            except Exception:
                pass
        try:
            with open(STATUS_PATH, "w") as f:
                json.dump({"status": text, "epoch": self.epoch,
                           "ts": time.time()}, f)
        except Exception:
            pass

    def _log(self, msg):
        line = "[%d] %s\n" % (time.time(), msg)
        try:
            with open(LOG_PATH, "a") as f:
                f.write(line)
        except Exception:
            pass

    # ---- lifecycle -------------------------------------------------------
    async def run(self):
        self.running = True
        self._set_status("booting")
        self._log("supervisor start")
        try:
            self._reload_payload()
        except Exception as e:
            self._set_status("payload-error")
            self._log("payload load failed: %r" % e)

        while self.running:
            t0 = time.ticks_ms()
            self.epoch += 1
            try:
                await self._epoch(t0)
            except Exception as e:
                self._log("epoch error: %r" % e)
                self._set_status("epoch-error")
            # Idle until next epoch (or until stopped), yielding to the GUI.
            remaining = self.epoch_ms - time.ticks_diff(time.ticks_ms(), t0)
            while remaining > 0 and self.running:
                await asyncio.sleep_ms(min(500, remaining))
                remaining -= 500

    async def _epoch(self, t0):
        self._set_status("collecting")
        # Phase 1: run the payload for this epoch (bounded by the epoch window)
        if self._ctx is None:
            self._ctx = PayloadContext(self._log, self.net,
                                       self.hw, self.epoch_ms)
        self._ctx.deadline_ms = time.ticks_add(t0, self.epoch_ms)
        res = self.payload.step(self._ctx)
        if res is not None and not hasattr(res, "send"):
            self._log("payload step returned error: %s" % res)
        elif res is not None:
            await res

        # Phase 2: sync upstream if a URL is configured
        if self.sync_url:
            await self._sync()
        else:
            self._set_status("idle (no sync_url)")

    async def _sync(self):
        self._set_status("connecting")
        if not self.net.connected:
            if not self.net.connect():
                self._set_status("offline: %s" % (self.net.last_error or "?"))
                return
        self.online = True
        self._set_status("syncing")
        # Build the telemetry batch (last N lines) and POST it.
        try:
            body = self._collect_batch()
            hdrs = {"Content-Type": "application/json"}
            status, data = self.net.request("POST", self.sync_url,
                                            body=body, headers=hdrs)
            if status == 200 and data:
                self._handle_upstream(data)
            else:
                self._set_status("sync-failed:%s" % status)
                self._log("sync status=%s data=%r" % (status, data[:120] if data else None))
        except Exception as e:
            self._set_status("sync-error")
            self._log("sync error: %r" % e)

    def _collect_batch(self):
        try:
            with open(LOG_PATH) as f:
                lines = f.readlines()[-500:]
        except Exception:
            lines = []
        return json.dumps({
            "device": "theorb",
            "epoch": self.epoch,
            "lines": [l.rstrip() for l in lines],
        })

    def _handle_upstream(self, data):
        """The backend may return a summary + a new payload. Hot-swap it."""
        try:
            reply = json.loads(data)
        except Exception:
            reply = {"status": "synced"}
        if isinstance(reply, dict):
            summary = reply.get("status") or reply.get("summary")
            if summary:
                self._set_status(str(summary)[:40])
            new_script = reply.get("agent_payload")
            if new_script:
                self._apply_new_payload(new_script)
        gc.collect()

    def _apply_new_payload(self, src):
        try:
            with open("agent_payload.py", "w") as f:
                f.write(src)
            self._log("new payload written (%d bytes)" % len(src))
            self._reload_payload()
        except Exception as e:
            self._log("payload apply failed: %r" % e)
            self._set_status("payload-write-error")

    def _reload_payload(self):
        try:
            self.payload.load(self._ctx or
                              PayloadContext(self._log, self.net, self.hw,
                                             self.epoch_ms))
            self._log("payload loaded: %s" % self.payload.name)
        except Exception as e:
            self._set_status("payload-error")
            self._log("payload load failed: %r" % e)

    def stop(self):
        self.running = False
        try:
            self.net.close()
        except Exception:
            pass
