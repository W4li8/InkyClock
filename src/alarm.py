"""
alarm.py -- alarm state machine: default time, the long-press-B digit
editor, and the "is it time to ring" check.

Button *reading* (debouncing, long-press timing) lives in main.py; this
module only reacts to the discrete events main.py feeds it (adjust_digit,
next_digit, enter_edit, start/stop_ringing).

To change the default alarm time or long-press/blink timing, see
config.DEFAULT_ALARM_HOUR/MINUTE, config.ALARM_LONG_PRESS_S,
config.ALARM_BLINK_PERIOD_S.

Long-press C (from MODE_CLOCK) toggles self.enabled -- see toggle_enabled()
and check_ring() below. main.py shows the enabled/disabled state on screen
(display.show_clock's alarm_enabled param).

Known limitation: if the alarm's own trigger minute passes while you happen
to be mid-edit (MODE_EDIT), it won't fire -- check_ring() is only evaluated
in MODE_CLOCK. Rare in practice (editing the alarm takes seconds), but real;
see todo.txt.
"""

import time

import config

MODE_CLOCK = "clock"
MODE_EDIT = "edit"
MODE_RINGING = "ringing"


class Alarm:
    def __init__(self):
        self.hour = config.DEFAULT_ALARM_HOUR
        self.minute = config.DEFAULT_ALARM_MINUTE
        self.enabled = True
        self.mode = MODE_CLOCK
        self.digit_index = 0  # 0=hour tens, 1=hour ones, 2=minute tens, 3=minute ones
        self._blink_on = True
        self._last_blink_ticks = time.ticks_ms()
        self._last_ring_minute_key = None  # (y, mo, d, hh, mm) already rung, avoid re-firing

    # -- entering / leaving edit mode -------------------------------------
    def enter_edit(self):
        """Long-press B (config.ALARM_LONG_PRESS_S) from MODE_CLOCK."""
        self.mode = MODE_EDIT
        self.digit_index = 0
        self._blink_on = True
        self._last_blink_ticks = time.ticks_ms()

    def _exit_edit(self):
        self.mode = MODE_CLOCK

    # -- enable / disable ---------------------------------------------------
    def toggle_enabled(self):
        """Long-press C (config.ALARM_LONG_PRESS_S) from MODE_CLOCK. Doesn't
        touch hour/minute/mode -- just whether check_ring() can ever fire."""
        self.enabled = not self.enabled

    # -- digit editing -------------------------------------------------
    def next_digit(self):
        """
        Short-press B while editing: advance to the next digit. Cycling
        through all 4 (hour tens -> hour ones -> minute tens -> minute
        ones) and pressing B once more on the last one saves and returns
        to the clock view.
        """
        if self.digit_index < 3:
            self.digit_index += 1
            self._blink_on = True
            self._last_blink_ticks = time.ticks_ms()
        else:
            self._exit_edit()

    def adjust_digit(self, delta):
        """
        delta=+1 for button A, -1 for button C. Adds/subtracts the selected
        digit's place value (10s or 1s) to the hour or minute it belongs to,
        wrapping mod 24 (hour) / mod 60 (minute) -- this always stays a
        valid time, at the cost of the "tens" digit occasionally carrying
        the display across a bigger jump than 1 at the 24/60 wraparound
        (e.g. hour tens digit on 17 -> +10 -> 03, not an invalid 27).
        """
        place = {0: 10, 1: 1, 2: 10, 3: 1}[self.digit_index]
        if self.digit_index < 2:
            self.hour = (self.hour + delta * place) % 24
        else:
            self.minute = (self.minute + delta * place) % 60

    def update_blink(self):
        """Call every main-loop tick while in MODE_EDIT."""
        now = time.ticks_ms()
        if time.ticks_diff(now, self._last_blink_ticks) >= config.ALARM_BLINK_PERIOD_S * 1000:
            self._blink_on = not self._blink_on
            self._last_blink_ticks = now

    @property
    def blink_visible(self):
        return self._blink_on

    # -- ring check -------------------------------------------------------
    def check_ring(self, now_tuple):
        """
        now_tuple = (year, month, day, hour, minute, second) from the RTC.
        Returns True the first time `now` matches the alarm time (won't
        re-fire again until the minute changes, even if dismissed and the
        same minute is still ticking). Always False while self.enabled is
        False (toggle_enabled(), long-press C).
        """
        if not self.enabled:
            return False
        y, mo, d, hh, mm, _ss = now_tuple
        if hh == self.hour and mm == self.minute:
            key = (y, mo, d, hh, mm)
            if key != self._last_ring_minute_key:
                self._last_ring_minute_key = key
                return True
        return False

    def start_ringing(self):
        self.mode = MODE_RINGING

    def stop_ringing(self):
        """Any button press while MODE_RINGING dismisses -- see main.py."""
        self.mode = MODE_CLOCK
