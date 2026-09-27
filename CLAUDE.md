# InkyClock — Working Notes

Persistent lessons from bringing this project up on real hardware. Read before touching `src/` or the board.

## Hardware / firmware facts

- **This board needs Pimoroni's MicroPython, not stock.** `src/display.py` imports `picographics`/`pimoroni`, which are native modules only present in Pimoroni's build (`pimoroni-pico-rp2350` repo for RP2350 boards — the older `pimoroni-pico` repo is RP2040-only). `build/fetch_firmware.sh` downloads the right UF2; flash via `mpremote bootloader` (if already running any MicroPython, no physical BOOTSEL press needed) then copy the `.uf2` onto the `RP2350`/`RPI-RP2` mass-storage drive that appears.
- **GP-number ≠ physical pin number.** GP22 is physical header pin 29, not pin 22 (physical pin 22 is GP17, already used for the display's CS). Always identify pins by "GP" number against the datasheet diagram (`docs/assets/`), never by counting header position.
- **The onboard LED on a `*_W` board is not on GP25** — it's routed through the CYW43 wireless chip. Use `machine.Pin("LED", Pin.OUT)`. Confirmed live: still works after `wlan.active(False)` (radio powered down).
- **No battery-backed RTC.** `machine.RTC()` resets to a power-on default (2021-01-01-ish) on every reset/power-loss. `main.py` always does a blocking boot-time sync rather than waiting for the next scheduled slot, for exactly this reason.
- **RP2350's internal temp sensor (`machine.ADC(4)`) works on this firmware** (a known 2024-era MicroPython/RP2350 bug elsewhere doesn't apply here), but it reads chip die temperature (self-heating from CPU/USB regulator), not room temperature — not usable for ambient sensing.
- **`PicoGraphics.text()` requires an integer `scale`** — raises `TypeError` on a float, even though `measure_text()` silently accepts one. Any scale-fitting search must use integer steps only (see `display.py`'s `_fit_scale`).
- **`machine.lightsleep(ms)` does not wake early on a button/GPIO interrupt on rp2.** The timed-sleep path explicitly gates off the GPIO clock domain before its one `__wfi()` call, and `Pin.irq()` has no `wake=` param on this port — only the timer alarm (or USB) ends it. Design idle sleep around a short fixed bound (`config.IDLE_LIGHTSLEEP_S`), not "sleep until an event." Full writeup: `docs/low-power.md`.
- **worldtimeapi.org is dead** (confirmed unreachable over HTTP and HTTPS from multiple networks). This project uses `timeapi.io`'s fixed-timezone endpoint instead — simpler too, returns already-broken-down local time, no epoch math needed.
- **f-strings are fully supported on this MicroPython build**, including format specs (`:02`, `:.2f`, etc.) — confirmed live. Use f-strings everywhere in this codebase, not `.format()` or `%`.

## Working with the board over `mpremote`

- **Any `mpremote exec` / `run` / `fs` command sends a break to the board first** to get raw-REPL control. If `main.py`'s loop (or its boot-time sync) is running, this **kills it** — including a single read-only status check. This caused a real multi-hour debugging detour: an interrupted boot sync left the RTC frozen at a stale-but-plausible value, which looked like "the clock is drifting" but was actually "the clock stopped getting corrected after being killed mid-sync."
  - After any such command, explicitly `mpremote reset` to put the board back in normal standalone operation — don't leave it sitting at a dead REPL prompt.
  - Don't chain another interrupting command immediately after a `reset` if you want to trust the result — a boot sync needs time to actually finish (observed: a few seconds when Wi-Fi/API are healthy, but `WIFI_CONNECT_TIMEOUT_S` alone allows up to 15s per attempt). Wait at least ~15-20s undisturbed before checking.
  - **Passively reading the port (no `mpremote` subcommand) does *not* send a break** and is safe for watching live `print()` output without killing anything — this is the non-invasive way to check "is it still running." Plain `cat /dev/tty.usbmodemXXXX` was unreliable in practice on macOS (silently captured nothing, or "Device not configured" right after a reset's USB re-enumeration); **`tools/serial_logger.py`** (pyserial-based) is what actually works — run it in the background (`nohup python3 tools/serial_logger.py &`) and it logs everything with timestamps for however long needed, surviving across turns/sessions. It holds the port open continuously, so kill it before any `mpremote` command and restart it after.
- `mpremote run test/test_X.py` executes a local test file directly without persisting it to the device — good for one-off checks. `build/flash.sh` is for actual deployment (copies `src/*.py`, then resets).
- The board enumerates as `/dev/tty.usbmodemXXXX` / `/dev/cu.usbmodemXXXX` on macOS; the exact number can change across reconnects.
- **Don't put a blocking wait inside a `display.py` view method.** An earlier throttle design blocked main.py's *entire loop* (button polling included) for up to 500ms after every screen update, causing a real, reported "feels like I need two clicks for anything" regression — a button press+release happening entirely during that block is invisible to `poll_button()`'s edge-detection, since the loop simply wasn't running. Fix: view methods only draw into the buffer (fast); a separate `push_if_due()`, called once per main-loop tick from `main.py` (not from inside a view method), does the actual throttled hardware push non-blockingly. Any future "rate-limit this hardware call" need on this project should follow that same split, not re-introduce a blocking wait in the draw path.

## Project conventions

- Every `src/*.py` hardware/logic module gets a matching `test/test_*.py`, runnable independently via `mpremote run` — see `test/README.md`.
- Debug logging: every module prints on its own actions (`[wifi]`, `[display]`, `[buzzer]`, `[main]` prefixes) — button presses, mode transitions, screen redraws, buzzer on/off, Wi-Fi connect/disconnect, API calls. This is what makes the passive-`cat` technique above actually useful for diagnosing "what happened" after the fact.
- `todo.txt` is a running, timestamped build log — append to it, don't rewrite history. `idea.txt` is a parking lot for out-of-scope feature ideas, not a task list.
- `src/secrets.py` is gitignored and must never be committed; `src/secrets.example.py` is the tracked template.
