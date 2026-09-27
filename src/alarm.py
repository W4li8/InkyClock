"""
alarm.py -- alarm state machine: default time, the long-press-B digit
editor, and the "is it time to ring" check.

Button *reading* (debouncing, long-press timing) lives in main.py; this
module only reacts to the discrete events main.py feeds it (adjust_digit,
next_digit, enter_edit, start/stop_ringing).

To change the default alarm time or long-press/blink timing, see
config.DEFAULT_ALARM_HOUR/MINUTE, config.ALARM_LONG_PRESS_S,
config.ALARM_BLINK_PERIOD_S, config.ALARM_EDIT_TIMEOUT_S.

Long-press B toggles MODE_CLOCK <-> MODE_EDIT (enter_edit() / exit_edit()).
Short-press B just cycles the selected digit 0->1->2->3->0->... forever --
editing never auto-exits on its own; you leave either by long-pressing B
again or by going idle for config.ALARM_EDIT_TIMEOUT_S (edit_idle_expired(),
polled from main.py).

Press C (any duration) shows the alarm time for config.ALARM_LONG_PRESS_S
seconds (start_preview() / preview_expired() / end_preview()) -- if you keep
holding for that whole window, main.py's long-press-C callback also fires
toggle_enabled() below, using the same window as the display timer. Short C
(outside MODE_EDIT/RINGING) does nothing extra; short C *during* MODE_EDIT
still decrements the selected digit via adjust_digit(), unrelated to preview.

Known limitation: if the alarm's own trigger minute passes while you happen
to be mid-edit (MODE_EDIT) or mid-preview (MODE_PREVIEW), it won't fire --
check_ring() is only evaluated in MODE_CLOCK. Rare in practice (a preview is
at most 3s; editing now can run up to config.ALARM_EDIT_TIMEOUT_S idle, so
marginally more exposure than before, but still real; see todo.txt.
"""

import time

import config

MODE_CLOCK = "clock"
MODE_EDIT = "edit"
MODE_RINGING = "ringing"
MODE_PREVIEW = "preview"


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
        self._last_edit_activity_ticks = None
        self._preview_start_ticks = None

    # -- entering / leaving edit mode -------------------------------------
    def enter_edit(self):
        """Long-press B from MODE_CLOCK."""
        self.mode = MODE_EDIT
        self.digit_index = 0
        self._blink_on = True
        self._last_blink_ticks = time.ticks_ms()
        self._last_edit_activity_ticks = time.ticks_ms()

    def exit_edit(self):
        """Long-press B again while MODE_EDIT (toggle), or edit_idle_expired()
        timing out -- either way just returns to the clock view. No separate
        "save" step needed: adjust_digit() already mutated hour/minute live."""
        self.mode = MODE_CLOCK

    def edit_idle_expired(self):
        """Call every tick while MODE_EDIT. True once
        config.ALARM_EDIT_TIMEOUT_S has passed with no next_digit()/
        adjust_digit() activity -- main.py then calls exit_edit()."""
        if self._last_edit_activity_ticks is None:
            return False
        return time.ticks_diff(time.ticks_ms(), self._last_edit_activity_ticks) >= config.ALARM_EDIT_TIMEOUT_S * 1000

    def _touch_edit_activity(self):
        self._last_edit_activity_ticks = time.ticks_ms()

    # -- enable / disable ---------------------------------------------------
    def toggle_enabled(self):
        """Fires from main.py's long-press-C callback (MODE_CLOCK or
        MODE_PREVIEW) once the press crosses config.ALARM_LONG_PRESS_S --
        the same window start_preview() is already timing the display for.
        Doesn't touch hour/minute/mode -- just whether check_ring() can fire."""
        self.enabled = not self.enabled

    # -- press-C preview ------------------------------------------------
    def start_preview(self):
        """Press C from MODE_CLOCK (any duration, see main.py's c_press):
        show the alarm time for config.ALARM_LONG_PRESS_S seconds regardless
        of how long C is actually held."""
        self.mode = MODE_PREVIEW
        self._preview_start_ticks = time.ticks_ms()

    def preview_expired(self):
        """Call every tick while MODE_PREVIEW. True once the display window
        (config.ALARM_LONG_PRESS_S, shared with the long-press-toggle
        threshold) has elapsed."""
        if self._preview_start_ticks is None:
            return True
        return time.ticks_diff(time.ticks_ms(), self._preview_start_ticks) >= config.ALARM_LONG_PRESS_S * 1000

    def end_preview(self):
        self.mode = MODE_CLOCK
        self._preview_start_ticks = None

    # -- digit editing -------------------------------------------------
    def next_digit(self):
        """Short-press B while editing: cycle to the next digit, wrapping
        0->1->2->3->0->... forever. See module docstring for how you
        actually leave edit mode now (it's not this)."""
        self.digit_index = (self.digit_index + 1) % 4
        self._blink_on = True
        self._last_blink_ticks = time.ticks_ms()
        self._touch_edit_activity()

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
        self._touch_edit_activity()

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
