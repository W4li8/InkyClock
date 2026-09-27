# Time Sync Design

How `src/wifi.py` keeps `machine.RTC()` accurate, and why it's built the way it is.

## Why an API instead of plain NTP

Plain NTP gives you UTC only — you'd still need to know the local UTC offset (and DST rules) yourself. Since the ask was "pull from a source that adjusts timezone," this project calls **[worldtimeapi.org](http://worldtimeapi.org/api/ip)** instead: `GET /api/ip` auto-detects timezone from the caller's public IP and returns both `unixtime` (UTC epoch) and `utc_offset` (e.g. `"+02:00"`), so the DST/timezone math is done server-side. Swap `config.TIME_API_URL` to `.../api/timezone/Area/City` to pin a fixed zone instead of IP geolocation, or point it at a different API/your own server — `wifi.py`'s parser just needs those same two JSON fields.

## The epoch gotcha

The API returns a standard **Unix** epoch (seconds since 1970-01-01). MicroPython's `time.localtime()` / `machine.RTC()` use the **MicroPython epoch** (2000-01-01) on most ports, including rp2. `wifi.py` subtracts the 946684800-second difference (`_UNIX_TO_MPY_EPOCH`) before converting — easy to get wrong if you ever touch that code, so it's called out explicitly there and here.

## Schedule: T0-anchored, 4-hourly, capped retries

Per the original spec: resync every 4 hours, anchored to a fixed time-of-day (`config.SYNC_T0_HOUR/MINUTE`, default 01:23 → slots at 01:23, 05:23, 09:23, 13:23, 17:23, 21:23). If a slot's sync fails, retry up to `config.SYNC_RETRY_COUNT` times (default 5), `config.SYNC_RETRY_INTERVAL_S` apart (default 60s). If all attempts in a slot fail, give up and keep the RTC's current value (the "local estimate") until the next slot — no continuous hammering.

## Blocking at boot, non-blocking after that

- **`TimeSync.sync_blocking()`** — used once at boot (`main.py`). Runs the full retry sequence immediately (regardless of the T0 schedule) so the clock is right away rather than potentially wrong for hours until the next slot. This *does* block the main loop, but nothing else is running yet.
- **`TimeSync.poll()`** — used every main-loop tick thereafter. It's a small state machine: does nothing until a slot is due, then performs **one** attempt per call (so each call only blocks for a single HTTP request, not the whole 5-minute worst case), scheduling the next retry via a timestamp rather than `time.sleep()`. This keeps button presses and the alarm check responsive even while a resync is failing/retrying in the background — see `main.py`'s main loop, which explicitly skips calling `poll()` while `MODE_RINGING` so a resync in progress can never delay dismissing the alarm.

## Known gap

No persistent/battery-backed RTC (see `idea.txt`) means a boot with Wi-Fi down leaves the clock wrong until the network recovers — there's no offline fallback baseline. An external RTC module would fix that; not implemented here.
