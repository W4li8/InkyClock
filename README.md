# InkyClock

MicroPython alarm clock for a Pico 2 W + Pimoroni Pico Inky Pack. Shows a big 24h clock (+ date), syncs time over Wi-Fi every 4h, and has a long-press digit editor for the alarm.

**Setup:** copy `src/secrets.example.py` → `src/secrets.py`, fill in your Wi-Fi creds, install `urequests` (`mip install urequests`), copy everything in `src/` to the Pico's filesystem root.

To modify... | see
---|---
Wi-Fi creds | `src/secrets.py` (`WIFI_SSID`, `WIFI_PASSWORD`)
Time-sync API, schedule (T0/interval/retries) | `src/config.py` (`TIME_API_URL`, `SYNC_*`)
Default alarm time, long-press duration, blink speed | `src/config.py` (`DEFAULT_ALARM_*`, `ALARM_LONG_PRESS_S`, `ALARM_BLINK_PERIOD_S`)
Any GPIO pin assignment | `src/pins.py`
How Wi-Fi connects / the actual sync HTTP call | `src/wifi.py` (`connect()`, `TimeSync._fetch_local_datetime()`)
Clock/date layout, alarm-edit view, ring-flash border | `src/display.py` (`InkyDisplay.show_clock`, `show_alarm_edit`, `flash_alarm_border`)
Alarm digit-edit logic, ring trigger | `src/alarm.py` (`Alarm.adjust_digit`, `next_digit`, `check_ring`)
Alarm on/off (long-press C) | `src/alarm.py` (`Alarm.enabled`, `toggle_enabled`)
Low-power idle sleep / Wi-Fi radio power-down | `src/main.py` (tail of `main()`, `machine.lightsleep`), `src/wifi.py` (`radio_active`, `TimeSync._conclude`)
The real buzzer tune (once wired up) | `src/buzzer.py` (`BUZZER_CONNECTED`, `PassiveBuzzer.play_alarm_tune`)
Button behavior / main loop | `src/main.py` (`a_short`/`b_short`/`b_long`/`c_short`/`c_long`, `main()`)

Background/rationale for each piece: `docs/`. Build log: `todo.txt`. Parked feature ideas: `idea.txt`.
