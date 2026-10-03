"""
test/test_alarm.py -- LOGIC TEST: alarm.py's Alarm state machine.

No hardware needed beyond the flash filesystem (always present, used by the
persistence checks below):
    mpremote connect <port> run test/test_alarm.py

Exercises digit editing, wraparound, enable/disable, the ring-check gating,
and flash persistence -- the part of this project that's easiest to
silently break with an off-by-one and hardest to notice by eye on the
actual clock. Backs up any real state.json first and restores it
afterward, same as test_persist.py, so this doesn't clobber whatever the
real app has actually persisted (alarm settings AND the unrelated time
checkpoint living in the same file).

Several Alarm() instances get constructed back-to-back below, and
exit_edit()/toggle_enabled() now write to flash -- _clear_persisted() runs
after each one so an earlier instance's save doesn't leak into a later
instance's "starts at config default" assumption.
"""
import time

import uos

import config
import persist
from alarm import Alarm, MODE_CLOCK, MODE_EDIT, MODE_PREVIEW

print("=== test_alarm ===")
ok = True


def check(name, cond, detail=""):
    global ok
    if cond:
        print("PASS:", name)
    else:
        ok = False
        print("FAIL:", name, detail)


def _clear_persisted():
    try:
        uos.remove(persist.STATE_FILE)
    except OSError:
        pass


had_real_state = False
try:
    uos.stat(persist.STATE_FILE)
    had_real_state = True
    uos.rename(persist.STATE_FILE, persist.STATE_FILE + ".testbak")
except OSError:
    pass

try:
    _clear_persisted()

    a = Alarm()
    check("starts at config default time",
          (a.hour, a.minute) == (config.DEFAULT_ALARM_HOUR, config.DEFAULT_ALARM_MINUTE))
    check("starts enabled", a.enabled is True)
    check("starts in MODE_CLOCK", a.mode == MODE_CLOCK)

    a.enter_edit()
    check("enter_edit() -> MODE_EDIT", a.mode == MODE_EDIT)
    check("enter_edit() resets digit_index to 0", a.digit_index == 0)

    a.hour, a.minute = 7, 0
    a.digit_index = 0  # hour tens
    a.adjust_digit(+1)
    check("digit 0 (hour tens) +1 -> hour 17", a.hour == 17, f"got {a.hour}")
    a.adjust_digit(+1)
    check("digit 0 +1 again wraps 27->03 (mod 24)", a.hour == 3, f"got {a.hour}")

    a.hour = 23
    a.digit_index = 1  # hour ones
    a.adjust_digit(+1)
    check("digit 1 (hour ones) +1 wraps 23->00", a.hour == 0, f"got {a.hour}")

    a.minute = 50
    a.digit_index = 2  # minute tens
    a.adjust_digit(+1)
    check("digit 2 (minute tens) +1 wraps 50->00 (mod 60)", a.minute == 0, f"got {a.minute}")

    a.minute = 59
    a.digit_index = 3  # minute ones
    a.adjust_digit(+1)
    check("digit 3 (minute ones) +1 wraps 59->00", a.minute == 0, f"got {a.minute}")

    a2 = Alarm()
    a2.enter_edit()
    for expected in (1, 2, 3, 0, 1):
        a2.next_digit()
        check(f"next_digit() cycles to {expected} (wraps, never auto-exits)", a2.digit_index == expected)
    check("still in MODE_EDIT after cycling past the 4th digit", a2.mode == MODE_EDIT)
    a2.exit_edit()
    check("exit_edit() -> MODE_CLOCK", a2.mode == MODE_CLOCK)
    _clear_persisted()  # exit_edit() just saved -- clear it so it doesn't leak into instances below

    a2b = Alarm()
    a2b.enter_edit()
    check("edit_idle_expired() False right after entering", a2b.edit_idle_expired() is False)
    a2b._last_edit_activity_ticks = time.ticks_add(time.ticks_ms(), -int(config.ALARM_EDIT_TIMEOUT_S * 1000) - 100)
    check("edit_idle_expired() True once ALARM_EDIT_TIMEOUT_S has passed", a2b.edit_idle_expired() is True)
    a2b.adjust_digit(+1)
    check("adjust_digit() resets the idle timer", a2b.edit_idle_expired() is False)

    a3 = Alarm()
    was_enabled = a3.enabled
    a3.toggle_enabled()
    check("toggle_enabled() flips enabled", was_enabled is True and a3.enabled is False)
    _clear_persisted()  # toggle_enabled() just saved -- clear it so it doesn't leak into instances below

    a4 = Alarm()
    a4.hour, a4.minute = 7, 30
    now = (2026, 1, 1, 7, 30, 0)
    check("check_ring() fires on exact match", a4.check_ring(now) is True)
    check("check_ring() doesn't re-fire same minute", a4.check_ring(now) is False)

    a5 = Alarm()
    a5.hour, a5.minute = 7, 30
    a5.enabled = False
    check("check_ring() never fires while disabled", a5.check_ring((2026, 1, 1, 7, 30, 0)) is False)

    a6 = Alarm()
    a6.start_preview()
    check("start_preview() -> MODE_PREVIEW", a6.mode == MODE_PREVIEW)
    check("preview_expired() False right after starting", a6.preview_expired() is False)
    a6._preview_start_ticks = time.ticks_add(time.ticks_ms(), -int(config.ALARM_LONG_PRESS_S * 1000) - 100)
    check("preview_expired() True once ALARM_LONG_PRESS_S has passed", a6.preview_expired() is True)
    a6.end_preview()
    check("end_preview() -> MODE_CLOCK", a6.mode == MODE_CLOCK)

    # -- flash persistence ---------------------------------------------
    _clear_persisted()
    a7 = Alarm()
    check("no saved state -> falls back to config defaults",
          (a7.hour, a7.minute, a7.enabled) == (config.DEFAULT_ALARM_HOUR, config.DEFAULT_ALARM_MINUTE, True))

    a7.enter_edit()
    a7.hour, a7.minute = 6, 45
    a7.exit_edit()
    check("exit_edit() persisted hour/minute to flash",
          persist.load().get("alarm") == {"hour": 6, "minute": 45, "enabled": True})

    a8 = Alarm()
    check("next Alarm() restores the persisted hour/minute/enabled",
          (a8.hour, a8.minute, a8.enabled) == (6, 45, True))

    a8.toggle_enabled()
    check("toggle_enabled() persisted the flip",
          persist.load().get("alarm") == {"hour": 6, "minute": 45, "enabled": False})

    a9 = Alarm()
    check("restored enabled=False survives a fresh instance", a9.enabled is False)

    persist.update({"datetime": [2026, 1, 1, 3, 7, 30, 0]})  # simulate wifi.py's unrelated checkpoint
    a9.toggle_enabled()
    check("saving alarm settings doesn't clobber an unrelated persisted key (datetime)",
          persist.load().get("datetime") == [2026, 1, 1, 3, 7, 30, 0])

    _clear_persisted()
    with open(persist.STATE_FILE, "w") as f:
        f.write('{"alarm": "not a dict"}')
    a10 = Alarm()
    check("a corrupt/wrong-shape 'alarm' entry falls back to config defaults instead of raising",
          (a10.hour, a10.minute) == (config.DEFAULT_ALARM_HOUR, config.DEFAULT_ALARM_MINUTE),
          f"got hour={a10.hour} minute={a10.minute}")

    print("PASS: all alarm.py checks passed" if ok else "test_alarm: FAILED, see above")

finally:
    _clear_persisted()
    if had_real_state:
        uos.rename(persist.STATE_FILE + ".testbak", persist.STATE_FILE)
        print("(restored the real state.json that was here before this test)")
