# The Orb — Agentic Runtime Architecture

The device is an **agentic field node**: a static, frozen supervisor orchestrates
hardware while a remote agent (Docker-hosted FastAPI + LangGraph backend) rewrites
the behaviour payload over the air. Derived from `gemini_planning/theorbplanning.pdf`.

## Split: frozen vs. hot-swappable

| Layer | Where | Rationale |
|-------|-------|-----------|
| Drivers (cc1101, es8311, ft6x36, ili9341) | **Frozen in firmware** | Baked in; stable, survives payload swaps |
| GUI library (`gui/`, `touch/`) | **Frozen in firmware** | Saves RAM, no rebuild needed per UI tweak |
| Supervisor (`agent/`) | **Frozen in firmware** | Must survive a bad payload; owns all I/O |
| `main.py`, `screens.py`, `touch_setup.py` | **VFS** (`app/`) | App shell; editable without reflash |
| `agent_payload.py` | **VFS** | The hot-swap target the cloud agent rewrites |
| `config/`, `logs/` | **VFS** | Persistent state, known networks, rolling batches |

The fatal error to avoid: never let a pushed payload be able to brick the device.
Because the supervisor is frozen and the payload is isolated behind a fixed
contract, a broken `agent_payload.py` only fails its own epoch — the device keeps
booting and syncs the traceback home.

## Files (frozen)

```
agent/
  supervisor.py   Static orchestrator. Async run() = epoch loop:
                    collect -> sync -> analyse -> re-arm
                  Owns Net, Payload, status broadcast, config.
  net.py          Network cascade (known WPA2 -> open) + HTTPS transport.
                  Refuses http:// unless allow_insecure.
  runner.py       Payload loader/validator/hot-swap. PayloadContext = the only
                  surface a payload gets (log, net, hw, state, emit_status).
  __init__.py     exports Supervisor
```

## Files (VFS `app/`)

```
main.py           import touch_setup; Screen.change(screens.BaseScreen)
screens.py        BaseScreen (menu) + AgentScreen (live status)
touch_setup.py    ILI9341 + FT6336 init -> Display
agent_payload.py  DEFAULT payload; overwritten by the cloud agent
config/
  supervisor.json  epoch_ms, sync_url, net_timeout
  known_nets.json  SSID -> password map
```

## Epoch lifecycle (supervisor.run)

1. **Collect** — `payload.step(ctx)` runs the current payload. It sees
   `ctx.time_left_ms()` and must return before the epoch deadline. Sync or async.
2. **Sync** — if `sync_url` is set, run the network cascade, POST the last 500
   log lines as JSON, receive a reply.
3. **Analyse / re-arm** — the reply may contain:
   - `status` / `summary` -> shown on screen
   - `agent_payload` (source string) -> written to `agent_payload.py`, reloaded
     immediately. This is the agent rewriting its own monitoring logic.
4. **Idle** — sleep to the next epoch in 500ms slices (GUI keeps running).

## Payload contract

```python
MODULE_NAME = "subghz-scan"      # shown in UI
def setup(ctx): ...              # optional, once per load
def run(ctx): ...                # once per epoch (sync or async)
def teardown(ctx): ...           # optional, before unload
```

`ctx` surface: `log(msg)`, `emit_status(str)`, `time_left_ms()`, `state` (dict
persisting across epochs), `hw` (shared handles), `net` (offline-safe manager).

## Upstream API shape (what your FastAPI/LangGraph backend should implement)

`POST {sync_url}` with body:
```json
{"device":"theorb","epoch":42,"lines":["[ts] ...", "..."]}
```
Response (JSON):
```json
{
  "status": "short line for the screen",
  "agent_payload": "MODULE_NAME='x'\ndef run(ctx): ..."
}
```
- Omit `agent_payload` to keep the current script.
- Return the full script source; the device writes and reloads it.

## Safety properties

- **No-brick**: supervisor + drivers frozen; payload isolated via `runner`.
- **Transport**: HTTPS enforced unless `allow_insecure` explicitly passed.
- **Never hangs**: network connect has a timeout; sync wrapped in try/except;
  epoch errors are logged and the loop continues.
- **Memory**: `gc.collect()` around payload swaps; PSRAM-backed 13MB VFS for logs.

## Threading / async model

`micropython-touch` owns one asyncio loop (`auto_refresh`, `_touchtest`).
`AgentScreen` registers `supervisor.run()` and a 250ms UI-refresh coroutine via
`Screen.reg_task`. Both are cancelled on screen leave (`on_hide` calls
`supervisor.stop()`). The supervisor never calls `run_until_complete` from inside
this loop — payload coroutines are awaited directly.

## Not yet built (roadmap)

- Real CC1101 sampling in the payload: done — `frozen/modules/cc1101.py`
  (driver) + `frozen/modules/subghz.py` (decode + capture store) +
  `app/agent_payload.py`, which sweeps 315/433.92/868 MHz, reports the RSSI
  peak, then grabs, decodes, and saves one raw OOK capture (see
  `docs/HARDWARE_REFERENCE.md` for wiring and the EV1527/PT2262 decoder). The
  on-device Sub-GHz screen also captures, decodes, and browses `/captures`.
  Next: more protocols (PWM encodings, rolling codes) and optional RF replay
  (blocked: OOK TX needs the I2C-shared GDO0).
- SD-card mount (board uses SDIO; VFS currently in internal 13MB flash).
- BLE/hotspot dual-radio decision (see planning doc §secondary NIC).
- Backend: FastAPI ingest + LangGraph + RAG (separate repo).
- Golden-path test: mock Net, run one epoch on host CPython with stubs.
