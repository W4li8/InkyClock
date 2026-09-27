"""
test/test_alarm.py -- LOGIC TEST: alarm.py's Alarm state machine.

No hardware needed:
    mpremote connect <port> run test/test_alarm.py

Exercises digit editing, wraparound, enable/disable, and the ring-check
gating -- the part of this project that's easiest to silently break with an
off-by-one and hardest to notice by eye on the actual clock.
"""
import config
from alarm import Alarm, MODE_CLOCK, MODE_EDIT

print("=== test_alarm ===")
ok = True


def check(name, cond, detail=""):
    global ok
    if cond:
        print("PASS:", name)
    else:
        ok = False
        print("FAIL:", name, detail)


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
check("digit 0 (hour tens) +1 -> hour 17", a.hour == 17, "got {}".format(a.hour))
a.adjust_digit(+1)
check("digit 0 +1 again wraps 27->03 (mod 24)", a.hour == 3, "got {}".format(a.hour))

a.hour = 23
a.digit_index = 1  # hour ones
a.adjust_digit(+1)
check("digit 1 (hour ones) +1 wraps 23->00", a.hour == 0, "got {}".format(a.hour))

a.minute = 50
a.digit_index = 2  # minute tens
a.adjust_digit(+1)
check("digit 2 (minute tens) +1 wraps 50->00 (mod 60)", a.minute == 0, "got {}".format(a.minute))

a.minute = 59
a.digit_index = 3  # minute ones
a.adjust_digit(+1)
check("digit 3 (minute ones) +1 wraps 59->00", a.minute == 0, "got {}".format(a.minute))

a2 = Alarm()
a2.enter_edit()
for expected in (1, 2, 3):
    a2.next_digit()
    check("next_digit() advances to {}".format(expected), a2.digit_index == expected)
a2.next_digit()
check("next_digit() past the 4th digit exits to MODE_CLOCK", a2.mode == MODE_CLOCK)

a3 = Alarm()
was_enabled = a3.enabled
a3.toggle_enabled()
check("toggle_enabled() flips enabled", was_enabled is True and a3.enabled is False)

a4 = Alarm()
a4.hour, a4.minute = 7, 30
now = (2026, 1, 1, 7, 30, 0)
check("check_ring() fires on exact match", a4.check_ring(now) is True)
check("check_ring() doesn't re-fire same minute", a4.check_ring(now) is False)

a5 = Alarm()
a5.hour, a5.minute = 7, 30
a5.enabled = False
check("check_ring() never fires while disabled", a5.check_ring((2026, 1, 1, 7, 30, 0)) is False)

print("PASS: all alarm.py checks passed" if ok else "test_alarm: FAILED, see above")
