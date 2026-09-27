"""
persist.py -- small helper for saving/restoring state across reboots using
the Pico's onboard flash filesystem. No extra hardware needed (see
idea.txt's reboot-persistence and external-RTC-module entries).

Important limitation, not a bug to fix here: this survives a reboot or
power-cycle, but has no idea how long the power was actually off -- a
restored value is "the last thing we saw", never corrected for the outage
duration. Only a real battery-backed RTC module knows elapsed time through
an actual power loss; this is a "less wrong than the hardcoded default"
fallback, not a replacement for that.

A missing or corrupt file is treated as "no saved state" (returns {}),
since that's the ordinary first-boot case, not an error worth surfacing.
"""
import ujson

STATE_FILE = "state.json"


def load():
    """Return the saved state dict, or {} if there isn't one / it's unreadable."""
    try:
        with open(STATE_FILE) as f:
            return ujson.load(f)
    except (OSError, ValueError) as exc:
        print("[persist] no usable saved state:", exc)
        return {}


def save(state):
    """Overwrite the saved state file with `state` (a plain dict)."""
    try:
        with open(STATE_FILE, "w") as f:
            ujson.dump(state, f)
    except OSError as exc:
        print("[persist] failed to save state:", exc)
