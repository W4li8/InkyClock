# InkyClock

MicroPython alarm clock for a Pico 2 W + Pimoroni Pico Inky Pack. Shows a big 24h clock (+ date), syncs time over Wi-Fi every 4h, and has a long-press digit editor for the alarm.

**Setup:** copy `src/secrets.example.py` → `src/secrets.py`, fill in your Wi-Fi creds, flash Pimoroni's MicroPython (`build/fetch_firmware.sh`, not stock MicroPython — see `docs/pico-inky-pack.md`), then `build/flash.sh` to deploy. `test/` has one independently-runnable check per `src/*.py` module (`test/README.md`) — worth running after any change, especially `test_pins`/`test_config`/`test_alarm` (no hardware needed) before bothering with the ones that need eyes/ears on the board.

To modify... | see
---|---
Wi-Fi creds | `src/secrets.py` (`WIFI_SSID`, `WIFI_PASSWORD`)
Time-sync API, schedule (T0/interval/retries) | `src/config.py` (`TIME_API_URL`, `SYNC_*`)
Default alarm time, long-press duration, edit idle-timeout | `src/config.py` (`DEFAULT_ALARM_*`, `ALARM_LONG_PRESS_S`, `ALARM_EDIT_TIMEOUT_S`)
Any GPIO pin assignment | `src/pins.py`
How Wi-Fi connects / the actual sync HTTP call | `src/wifi.py` (`connect()`, `TimeSync._fetch_local_datetime()`)
Clock/date layout, alarm-edit view, alarm-preview view, ring-flash border | `src/display.py` (`InkyDisplay.show_clock`, `show_alarm_edit`, `show_alarm_preview`, `flash_alarm_border`)
Alarm digit-edit logic (cycles forever; long-B or idle-timeout exits), ring trigger | `src/alarm.py` (`Alarm.adjust_digit`, `next_digit`, `enter_edit`/`exit_edit`, `edit_idle_expired`, `check_ring`)
Alarm on/off + press-C time preview | `src/alarm.py` (`Alarm.enabled`, `toggle_enabled`, `start_preview`/`preview_expired`/`end_preview`)
Low-power idle tick / Wi-Fi radio power-down (NOT `machine.lightsleep` — see `CLAUDE.md`) | `src/main.py` (tail of `main()`, `config.IDLE_TICK_S`), `src/wifi.py` (`radio_active`, `TimeSync._conclude`)
The real buzzer tune (once wired up) | `src/buzzer.py` (`BUZZER_CONNECTED`, `PassiveBuzzer.play_alarm_tune`)
Button behavior / main loop | `src/main.py` (`a_short`/`b_short`/`b_long`/`c_press`/`c_short`/`c_long`, `poll_button`, `main()`)
Display refresh throttling (non-blocking, see `CLAUDE.md`) | `src/display.py` (`push_if_due`), `src/main.py` (called once per loop tick)
Watching the board for hours without disturbing it | `tools/serial_logger.py` (background, timestamped log — see `CLAUDE.md`)

Background/rationale for each piece: `docs/`. Per-module hardware/logic tests: `test/`. Build log: `todo.txt`. Parked feature ideas: `idea.txt`. Hardware/tooling gotchas: `CLAUDE.md`.
