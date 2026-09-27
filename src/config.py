"""
config.py -- non-secret project settings (safe to commit).

Wi-Fi credentials live in secrets.py instead, which is gitignored -- see
secrets.example.py for the template.
"""

# --- Time sync ---------------------------------------------------------
# timeapi.io's fixed-timezone endpoint -- change "timeZone=" to your own IANA
# zone name. (worldtimeapi.org, the original pick, was confirmed dead during
# hardware bring-up -- see docs/time-sync.md. This endpoint needs a fixed
# zone rather than auto-detecting from IP, which is a fine trade: this
# project already resyncs every 4h regardless.) wifi.py's parser expects
# timeapi.io's schema (plain year/month/day/hour/minute/seconds fields) --
# swapping providers means updating that parser too.
TIME_API_URL = "https://timeapi.io/api/time/current/zone?timeZone=America/Los_Angeles"

SYNC_INTERVAL_S = 4 * 60 * 60   # resync every 4 hours
SYNC_T0_HOUR = 1                 # first resync slot of the day: 01:23, then
SYNC_T0_MINUTE = 23              # 05:23, 09:23, 13:23, 17:23, 21:23
SYNC_RETRY_COUNT = 5             # total attempts per slot (not 5 retries *after* a first try)
SYNC_RETRY_INTERVAL_S = 60       # gap between attempts within one slot

WIFI_CONNECT_TIMEOUT_S = 15
WIFI_HOSTNAME = "inkypico"   # advertised via network.hostname(), see wifi.connect()

# Goal: don't miss the alarm by more than ~10 minutes if power comes back
# but Wi-Fi/the router is still down (routers often take longer to reboot
# than the Pico does). This only bounds the error to ~10 min for a BRIEF
# power outage -- persist.py has no way to track elapsed time while
# actually powered off, so a longer outage adds its own full duration on
# top of this, uncorrected (only a battery-backed RTC or UPS, see idea.txt,
# actually solves that case). Every successful Wi-Fi sync also checkpoints
# immediately regardless of this interval, so this constant only bounds the
# gap *between* syncs -- see persist.py, wifi.TimeSync.maybe_checkpoint.
PERSIST_CHECKPOINT_S = 10 * 60   # 10 minutes

# --- Alarm ---------------------------------------------------------------
DEFAULT_ALARM_HOUR = 7
DEFAULT_ALARM_MINUTE = 0
ALARM_LONG_PRESS_S = 3.0        # hold B/C this long to toggle edit mode / show+toggle alarm enabled
ALARM_EDIT_TIMEOUT_S = 15       # auto-exit MODE_EDIT after this long with no A/B/C activity
ALARM_RING_FLASH_HZ = 2         # requested border-flash rate; see display.py
                                 # docstring for why e-ink won't quite hit this

# --- Main loop -------------------------------------------------------------
# Both are plain time.sleep_ms(), NOT machine.lightsleep() -- confirmed live
# that lightsleep() freezes machine.RTC() for its entire duration on this
# board/firmware, which is a correctness bug, not just a power-saving
# nicety gone wrong. See docs/low-power.md.
MAIN_LOOP_TICK_S = 0.02         # active tick: editing, ringing, radio on, or a button currently held
IDLE_TICK_S = 0.25              # idle tick: MODE_CLOCK, nothing held -- bounded short so a button
                                 # press is still picked up promptly, not for any lightsleep-wake reason

# --- Power-on heartbeat -----------------------------------------------------
# Doubles as a live Wi-Fi-status indicator: fast while connected/syncing,
# slow the rest of the time (idle).
HEARTBEAT_WIFI_HZ = 5             # blink rate while wifi.radio_active()
HEARTBEAT_IDLE_HZ = 0.5           # blink rate otherwise
