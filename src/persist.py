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

One file, multiple unrelated callers (wifi.py's time checkpoint, alarm.py's
settings): save() REPLACES the whole file, so two callers each doing
save({"their_key": ...}) would clobber each other's key. Use update()
instead whenever you're not deliberately rewriting the entire state --
it's a read-merge-write so each caller's key survives independently.
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
    """Overwrite the saved state file with `state` (a plain dict). Prefer
    update() unless you actually mean to discard every other key."""
    try:
        with open(STATE_FILE, "w") as f:
            ujson.dump(state, f)
    except OSError as exc:
        print("[persist] failed to save state:", exc)


def update(partial):
    """Merge `partial`'s top-level keys into the existing saved state and
    write it back -- read-modify-write, so unrelated keys (e.g. alarm
    settings vs. the time checkpoint) don't clobber each other."""
    state = load()
    state.update(partial)
    save(state)
