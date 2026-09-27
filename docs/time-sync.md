# Time Sync Design

How `src/wifi.py` keeps `machine.RTC()` accurate, and why it's built the way it is.

## Why an API instead of plain NTP

Plain NTP gives you UTC only — you'd still need to know the local UTC offset (and DST rules) yourself. Since the ask was "pull from a source that adjusts timezone," this project calls a time API instead, one that does the DST/timezone math server-side.

**Originally worldtimeapi.org, switched to [timeapi.io](https://timeapi.io) during hardware bring-up.** worldtimeapi.org's `/api/ip` was the initial pick (auto-detects timezone from the caller's public IP, no zone to configure) — but during actual board testing it turned out to be **dead**: unreachable over both HTTP and HTTPS, confirmed from two independent networks (curl gave connection errors on both, while DNS still resolved and every other site worked fine). Long-known reliability problems with that free community service, apparently terminal by 2026.

`config.TIME_API_URL` now points at `https://timeapi.io/api/time/current/zone?timeZone=America/Los_Angeles` — a fixed-zone endpoint (change the `timeZone=` query param to your own [IANA zone name](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)). No IP-geolocation auto-detect this time around, but that's a fine trade: this project already resyncs every 4 hours regardless, so pinning a zone costs nothing in practice. Confirmed live on the actual board: `urequests` on this firmware handles HTTPS (not just HTTP) fine, so the switch from `http://` to `https://` needed no other changes.

If you swap providers again, `wifi.py`'s `_fetch_local_datetime()` parser needs updating to match — it's provider-schema-specific, not generic.

## No epoch math needed (this API returns broken-down local time directly)

timeapi.io's response is already local time for the requested zone, broken into plain `year`/`month`/`day`/`hour`/`minute`/`seconds` fields (plus a `dayOfWeek` name, mapped to an int via `_WEEKDAY_FROM_NAME` in `wifi.py`) — no Unix-epoch-to-MicroPython-epoch conversion required, unlike the old worldtimeapi.org integration. One less gotcha to get wrong.

## Schedule: T0-anchored, 4-hourly, capped retries

Per the original spec: resync every 4 hours, anchored to a fixed time-of-day (`config.SYNC_T0_HOUR/MINUTE`, default 01:23 → slots at 01:23, 05:23, 09:23, 13:23, 17:23, 21:23). If a slot's sync fails, retry up to `config.SYNC_RETRY_COUNT` times (default 5), `config.SYNC_RETRY_INTERVAL_S` apart (default 60s). If all attempts in a slot fail, give up and keep the RTC's current value (the "local estimate") until the next slot — no continuous hammering.

## Blocking at boot, non-blocking after that

- **`TimeSync.sync_blocking()`** — used once at boot (`main.py`). Runs the full retry sequence immediately (regardless of the T0 schedule) so the clock is right away rather than potentially wrong for hours until the next slot. This *does* block the main loop, but nothing else is running yet.
- **`TimeSync.poll()`** — used every main-loop tick thereafter. It's a small state machine: does nothing until a slot is due, then performs **one** attempt per call (so each call only blocks for a single HTTP request, not the whole 5-minute worst case), scheduling the next retry via a timestamp rather than `time.sleep()`. This keeps button presses and the alarm check responsive even while a resync is failing/retrying in the background — see `main.py`'s main loop, which explicitly skips calling `poll()` while `MODE_RINGING` so a resync in progress can never delay dismissing the alarm.

## Known gap

No persistent/battery-backed RTC (see `idea.txt`) means a boot with Wi-Fi down leaves the clock wrong until the network recovers — there's no offline fallback baseline. An external RTC module would fix that; not implemented here.
