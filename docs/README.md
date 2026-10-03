# InkyClock — Hardware Docs

Reference material pulled in while figuring out how to add an alarm buzzer to a Pico 2 W + Pimoroni Pico Inky Pack.

- [`pico-2-w-pinout.md`](pico-2-w-pinout.md) — full GPIO table, which pins the wireless chip claims, free-pin summary
- [`pico-inky-pack.md`](pico-inky-pack.md) — which pins the display/buttons use, which are free
- [`buzzer-notes.md`](buzzer-notes.md) — active vs. passive buzzer, wiring, `machine.PWM` API, example code
- [`debug-port-swd.md`](debug-port-swd.md) — what the 3-pin SWD debug header is/isn't for
- [`time-sync.md`](time-sync.md) — how the 4h/T0/retry time-sync schedule works, why worldtimeapi.org got dropped for timeapi.io, blocking-vs-non-blocking
- [`low-power.md`](low-power.md) — Wi-Fi-off-between-syncs (the real win); why `machine.lightsleep()` was tried and then dropped entirely — it freezes `machine.RTC()`, confirmed live, the actual root cause behind a lot of this project's "clock stopped" debugging
- [`pimoroni-examples/`](pimoroni-examples/) — official Pimoroni MicroPython examples for the Inky Pack (`button_test.py`, `clock.py`), copied from [pimoroni/pimoroni-pico](https://github.com/pimoroni/pimoroni-pico), useful as a starting point for the alarm UI
- [`assets/`](assets/) — pinout diagrams rendered from the official Raspberry Pi Pico 2 W datasheet PDF
- [`../src/pins.py`](../src/pins.py) — single source of truth for every pin assignment in this project (display, buttons, buzzer, free pins) — import from it instead of hardcoding GPIO numbers

## TL;DR

- Inky Pack has no speaker/buzzer — add an external passive piezo buzzer (and/or an I2S amp for real audio).
- Recommended pin: **GP22** (free, own PWM slice, right next to a GND pad) — see `src/pins.py`.
- Want it louder for free? Bridge-tie it across **GP8 + GP9** (same PWM slice, hardware-synced antiphase) — see `buzzer-notes.md`.
- Inky Pack uses GP12/13/14 (buttons) and GP17–21 + GP26 (display SPI/DC/RESET/BUSY) — avoid those.
- Pico 2 W's wireless chip claims GP23/24/25/29 internally — not available on the header at all.
- The 3-pin debug header (SWCLK/GND/SWDIO) is dedicated SWD silicon, not GPIO — can't drive anything, only useful for a hardware debug probe.
- Already have an I2S amp? Use it for the real alarm sound (proper audio, not a beep) and keep the piezo as a cheap backup — see `buzzer-notes.md`.
