"""
wifi.py -- wireless connection access: joining Wi-Fi, and the periodic
time-sync HTTP call that keeps machine.RTC() close to real time.

Uses timeapi.io's fixed-timezone endpoint (config.TIME_API_URL) -- switched
from worldtimeapi.org (the original choice) after confirming it's actually
down: unreachable over both HTTP and HTTPS from two different networks
during hardware bring-up, see docs/time-sync.md. _fetch_local_datetime()
below parses timeapi.io's schema (plain year/month/day/hour/minute/seconds
fields, already local time for the configured zone -- no epoch math needed).
To change the timezone or point this at yet another API, see config.py
(TIME_API_URL, SYNC_* constants). To change Wi-Fi credentials, edit
secrets.py (copy secrets.example.py first -- secrets.py is gitignored).
"""

import time
import machine
import network

import config
from secrets import WIFI_SSID, WIFI_PASSWORD

try:
    import urequests as requests
except ImportError:
    requests = None  # sync attempts fail cleanly (see _fetch_local_datetime) if the lib isn't installed

_WEEKDAY_FROM_NAME = {
    "Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3,
    "Friday": 4, "Saturday": 5, "Sunday": 6,
}


def connect(timeout_s=None):
    """Join the configured Wi-Fi network. Returns the WLAN object on success, None on timeout."""
    timeout_s = config.WIFI_CONNECT_TIMEOUT_S if timeout_s is None else timeout_s
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print(f"[wifi] connecting to {WIFI_SSID}...")
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        start = time.ticks_ms()
        while not wlan.isconnected():
            if time.ticks_diff(time.ticks_ms(), start) > timeout_s * 1000:
                print(f"[wifi] connect timed out after {timeout_s}s")
                return None
            time.sleep_ms(200)
        print(f"[wifi] connected, ip={wlan.ifconfig()[0]}")
    else:
        print(f"[wifi] already connected, ip={wlan.ifconfig()[0]}")
    return wlan


def disconnect():
    print("[wifi] disconnecting, powering radio down")
    wlan = network.WLAN(network.STA_IF)
    wlan.disconnect()
    wlan.active(False)


def radio_active():
    """
    True while the Wi-Fi radio is powered on. TimeSync powers it down
    between sync attempts (see _conclude() below) since it's only needed in
    short bursts every few hours -- the CYW43439 draws real current
    (tens of mA) whenever active/associated. main.py checks this before
    deciding whether machine.lightsleep() is safe to use for the idle-loop
    delay (some rp2 W-board firmware has had issues lightsleeping with the
    radio mid-connection, so main.py falls back to a plain time.sleep()
    while this is True).
    """
    return network.WLAN(network.STA_IF).active()


class TimeSync:
    """
    Keeps machine.RTC() close to real time by calling config.TIME_API_URL on
    a 4h-aligned schedule (see config.SYNC_T0_HOUR/MINUTE, SYNC_INTERVAL_S).

    Two ways to drive it:
      - sync_blocking(): runs the full retry sequence right now, blocking.
        Used once at boot so the clock is right immediately (see main.py).
      - poll(): call every main-loop tick. Non-blocking except for the
        single HTTP request when an attempt is actually due, so a slow/failing
        API can't stall the alarm for minutes (see the worst-case note below).

    On total failure (all SYNC_RETRY_COUNT attempts) the RTC -- the "local
    estimate" -- is left untouched until the next scheduled slot.

    Low-power note: the radio is powered off (disconnect()) as soon as a
    slot's attempts conclude, one way or the other (_conclude()), and only
    powered back on for the next slot -- see radio_active().
    """

    def __init__(self):
        self.rtc = machine.RTC()
        self.last_sync_ok = False
        self._retrying = False
        self._attempts_used = 0
        self._next_attempt_ticks = None

    # -- schedule -----------------------------------------------------------
    def seconds_until_next_slot(self):
        """Seconds from now until the next SYNC_T0-aligned, SYNC_INTERVAL_S-spaced slot."""
        _, _, _, _, hh, mm, ss, _ = self.rtc.datetime()
        now_min = hh * 60 + mm
        t0_min = config.SYNC_T0_HOUR * 60 + config.SYNC_T0_MINUTE
        interval_min = config.SYNC_INTERVAL_S // 60
        elapsed = (now_min - t0_min) % interval_min
        remaining_min = (interval_min - elapsed) % interval_min
        if remaining_min == 0 and ss > 0:
            remaining_min = interval_min
        return remaining_min * 60 - ss

    # -- one attempt ----------------------------------------------------------
    def _fetch_local_datetime(self):
        """Return a (year, month, day, weekday, hour, minute, second) local-time tuple, or None."""
        if requests is None:
            print("[wifi] urequests not installed -- see README setup step")
            return None
        print("[wifi] GET", config.TIME_API_URL)
        try:
            r = requests.get(config.TIME_API_URL, timeout=10)
        except Exception as exc:
            print("[wifi] time API request failed:", exc)
            return None
        print("[wifi] response status:", r.status_code)
        try:
            data = r.json()
        except Exception as exc:
            print("[wifi] time API returned bad JSON:", exc)
            return None
        finally:
            r.close()

        try:
            y = int(data["year"])
            mo = int(data["month"])
            d = int(data["day"])
            hh = int(data["hour"])
            mm = int(data["minute"])
            ss = int(data["seconds"])
            wd = _WEEKDAY_FROM_NAME.get(data.get("dayOfWeek"), 0)
            return (y, mo, d, wd, hh, mm, ss)
        except Exception as exc:
            print("[wifi] time API response missing expected fields:", exc)
            return None

    def _attempt_once(self):
        """One connect + fetch + RTC-set attempt. Returns True on success."""
        wlan = connect()
        if wlan is None:
            print("[wifi] could not join Wi-Fi")
            return False
        result = self._fetch_local_datetime()
        if result is None:
            return False
        y, mo, d, wd, hh, mm, ss = result
        self.rtc.datetime((y, mo, d, wd, hh, mm, ss, 0))
        print(f"[wifi] time synced: {y:04}-{mo:02}-{d:02} {hh:02}:{mm:02}:{ss:02}")
        return True

    # -- public API ----------------------------------------------------------
    def _conclude(self, ok):
        """Shared end-of-sequence bookkeeping: power the radio back down
        (see radio_active() docstring) now that this slot's attempts, one
        way or another, are done."""
        self.last_sync_ok = ok
        self._retrying = False
        disconnect()
        return ok

    def sync_blocking(self):
        """Run the full retry sequence right now, blocking (boot-time use only)."""
        for attempt in range(1, config.SYNC_RETRY_COUNT + 1):
            print(f"[wifi] boot sync attempt {attempt}/{config.SYNC_RETRY_COUNT}")
            if self._attempt_once():
                return self._conclude(True)
            if attempt < config.SYNC_RETRY_COUNT:
                time.sleep(config.SYNC_RETRY_INTERVAL_S)
        print("[wifi] boot sync failed, keeping whatever the RTC already has")
        return self._conclude(False)

    def poll(self):
        """
        Call every main-loop tick. Non-blocking except for the single HTTP
        attempt when one is actually due. Worst case (all 5 attempts fail)
        this module stays "busy" for 4 * SYNC_RETRY_INTERVAL_S = 4 minutes,
        but each individual poll() call only blocks for one HTTP request
        (a few seconds at most), so button presses / the alarm check in
        main.py's loop are never stalled for more than that.
        """
        now = time.ticks_ms()

        if not self._retrying:
            if self.seconds_until_next_slot() <= 0:
                print("[wifi] scheduled sync slot reached, starting attempts")
                self._retrying = True
                self._attempts_used = 0
                self._next_attempt_ticks = None
            else:
                return

        if self._next_attempt_ticks is not None and time.ticks_diff(now, self._next_attempt_ticks) < 0:
            return  # not time yet for the next retry within this slot

        self._attempts_used += 1
        print(f"[wifi] sync attempt {self._attempts_used}/{config.SYNC_RETRY_COUNT}")
        ok = self._attempt_once()

        if ok:
            self._conclude(True)
            return

        if self._attempts_used >= config.SYNC_RETRY_COUNT:
            print("[wifi] all sync attempts failed, keeping local estimate until next slot")
            self._conclude(False)
            return

        self._next_attempt_ticks = time.ticks_add(now, config.SYNC_RETRY_INTERVAL_S * 1000)
