"""
main.py -- InkyClock entry point: button polling, mode dispatch, main loop.

Flow: boot -> show a status message -> block once on wifi.TimeSync.sync_blocking()
so the clock is right immediately -> loop forever polling buttons, the RTC,
and (non-blocking) the 4h resync schedule via wifi.TimeSync.poll().

Button behaviour (see alarm.py for the state machine these call into):
  - short A / short C : while MODE_EDIT, +1 / -1 on the selected digit.
                         while MODE_RINGING, dismiss.
  - short B            : while MODE_EDIT, advance to the next digit (saves
                          and exits after the 4th). While MODE_RINGING, dismiss.
  - long B (3s)         : while MODE_CLOCK, enter alarm-edit mode.
                          while MODE_RINGING, dismiss.

To change what "short" vs "long" press means, see config.ALARM_LONG_PRESS_S
and poll_button()/ButtonState below.
"""

import time
import machine

import config
import pins
import wifi
from display import InkyDisplay
from buzzer import PassiveBuzzer
from alarm import Alarm, MODE_CLOCK, MODE_EDIT, MODE_RINGING


class ButtonState:
    """Debounced press tracking for one pin, active-low with a pull-up."""

    def __init__(self, pin):
        self.pin = pin
        self.was_pressed = False
        self.press_start_ticks = None
        self.long_press_fired = False


def poll_button(state, short_press_cb=None, long_press_cb=None, long_press_s=None):
    """Call once per main-loop tick per button. Fires short_press_cb on
    release (unless a long press already fired), long_press_cb once as soon
    as the hold crosses long_press_s."""
    pressed = state.pin.value() == 0
    now = time.ticks_ms()

    if pressed and not state.was_pressed:
        state.press_start_ticks = now
        state.long_press_fired = False

    if pressed and long_press_cb and not state.long_press_fired:
        if long_press_s and time.ticks_diff(now, state.press_start_ticks) >= long_press_s * 1000:
            state.long_press_fired = True
            long_press_cb()

    if not pressed and state.was_pressed:
        if not state.long_press_fired and short_press_cb:
            short_press_cb()

    state.was_pressed = pressed


def main():
    display = InkyDisplay()
    buzzer = PassiveBuzzer()
    alarm = Alarm()
    time_sync = wifi.TimeSync()
    rtc = machine.RTC()

    button_a = machine.Pin(pins.BUTTON_A, machine.Pin.IN, pull=machine.Pin.PULL_UP)
    button_b = machine.Pin(pins.BUTTON_B, machine.Pin.IN, pull=machine.Pin.PULL_UP)
    button_c = machine.Pin(pins.BUTTON_C, machine.Pin.IN, pull=machine.Pin.PULL_UP)

    state_a = ButtonState(button_a)
    state_b = ButtonState(button_b)
    state_c = ButtonState(button_c)

    def a_short():
        if alarm.mode == MODE_EDIT:
            alarm.adjust_digit(+1)
        elif alarm.mode == MODE_RINGING:
            alarm.stop_ringing()
            buzzer.silence()

    def b_short():
        if alarm.mode == MODE_EDIT:
            alarm.next_digit()
        elif alarm.mode == MODE_RINGING:
            alarm.stop_ringing()
            buzzer.silence()

    def b_long():
        if alarm.mode == MODE_CLOCK:
            alarm.enter_edit()
        elif alarm.mode == MODE_RINGING:
            alarm.stop_ringing()
            buzzer.silence()

    def c_short():
        if alarm.mode == MODE_EDIT:
            alarm.adjust_digit(-1)
        elif alarm.mode == MODE_RINGING:
            alarm.stop_ringing()
            buzzer.silence()

    # Boot-time sync: block once so the clock is correct right away, instead
    # of waiting for the next scheduled 4h slot (see wifi.TimeSync docstring).
    display.show_message("Syncing time...")
    time_sync.sync_blocking()

    last_mode = alarm.mode
    last_drawn_minute_key = None   # (y, mo, d, hh, mm) last shown in MODE_CLOCK
    last_edit_state = None         # (hour, minute, digit_index, blink_visible) last shown in MODE_EDIT
    border_visible = True
    last_border_toggle_ticks = time.ticks_ms()

    while True:
        poll_button(state_a, short_press_cb=a_short)
        poll_button(state_b, short_press_cb=b_short, long_press_cb=b_long,
                    long_press_s=config.ALARM_LONG_PRESS_S)
        poll_button(state_c, short_press_cb=c_short)

        # Force a redraw on any mode transition, so we never leave a stale
        # view (e.g. the alarm editor) on screen after switching modes.
        if alarm.mode != last_mode:
            last_drawn_minute_key = None
            last_edit_state = None
            last_mode = alarm.mode
            if alarm.mode == MODE_RINGING:
                border_visible = True
                last_border_toggle_ticks = time.ticks_ms()

        # Don't let a resync attempt's HTTP call delay the ring itself.
        if alarm.mode != MODE_RINGING:
            time_sync.poll()

        year, month, day, _wd, hour, minute, second, _sub = rtc.datetime()

        if alarm.mode == MODE_CLOCK:
            if alarm.check_ring((year, month, day, hour, minute, second)):
                alarm.start_ringing()
            else:
                minute_key = (year, month, day, hour, minute)
                if minute_key != last_drawn_minute_key:
                    display.show_clock(hour, minute, year, month, day)
                    last_drawn_minute_key = minute_key

        elif alarm.mode == MODE_EDIT:
            alarm.update_blink()
            edit_state = (alarm.hour, alarm.minute, alarm.digit_index, alarm.blink_visible)
            if edit_state != last_edit_state:
                display.show_alarm_edit(*edit_state)
                last_edit_state = edit_state

        elif alarm.mode == MODE_RINGING:
            buzzer.play_alarm_tune()
            now_ms = time.ticks_ms()
            half_period_ms = int(1000 / config.ALARM_RING_FLASH_HZ / 2)
            if time.ticks_diff(now_ms, last_border_toggle_ticks) >= half_period_ms:
                border_visible = not border_visible
                last_border_toggle_ticks = now_ms
                display.flash_alarm_border(alarm.hour, alarm.minute, border_visible)

        time.sleep(config.MAIN_LOOP_TICK_S)


if __name__ == "__main__":
    main()
