"""
config.py -- non-secret project settings (safe to commit).

Wi-Fi credentials live in secrets.py instead, which is gitignored -- see
secrets.example.py for the template.
"""

# --- Time sync ---------------------------------------------------------
# Any endpoint returning JSON with "unixtime" (UTC epoch seconds) and
# "utc_offset" (e.g. "+02:00") works with wifi.py's parser as-is.
# worldtimeapi.org auto-detects timezone from the caller's public IP; pin a
# fixed zone instead if you don't want that (see docs/time-sync.md).
TIME_API_URL = "http://worldtimeapi.org/api/ip"
# TIME_API_URL = "http://worldtimeapi.org/api/timezone/Europe/Prague"

SYNC_INTERVAL_S = 4 * 60 * 60   # resync every 4 hours
SYNC_T0_HOUR = 1                 # first resync slot of the day: 01:23, then
SYNC_T0_MINUTE = 23              # 05:23, 09:23, 13:23, 17:23, 21:23
SYNC_RETRY_COUNT = 5             # total attempts per slot (not 5 retries *after* a first try)
SYNC_RETRY_INTERVAL_S = 60       # gap between attempts within one slot

WIFI_CONNECT_TIMEOUT_S = 15

# --- Alarm ---------------------------------------------------------------
DEFAULT_ALARM_HOUR = 7
DEFAULT_ALARM_MINUTE = 0
ALARM_LONG_PRESS_S = 3.0        # hold B this long to enter alarm-set mode
ALARM_BLINK_PERIOD_S = 0.6      # digit blink half-period while editing
ALARM_RING_FLASH_HZ = 2         # requested border-flash rate; see display.py
                                 # docstring for why e-ink won't quite hit this

# --- Main loop -------------------------------------------------------------
MAIN_LOOP_TICK_S = 0.02         # active tick: editing, ringing, radio on, or a button currently held
IDLE_LIGHTSLEEP_S = 0.25        # idle tick: MODE_CLOCK, nothing held, radio off -- see docs/low-power.md
                                 # for why this can't just be "sleep until next minute, wake on button"

# --- Power-on heartbeat -----------------------------------------------------
HEARTBEAT_HZ = 2                 # onboard LED blink rate, all modes -- "power is on" indicator
