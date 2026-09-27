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
  - long C (3s)         : while MODE_CLOCK, toggle the alarm on/off
                          (alarm.toggle_enabled(); shown as "ALARM OFF" on
                          screen when off, see display.show_clock).
                          while MODE_RINGING, dismiss.

To change what "short" vs "long" press means, see config.ALARM_LONG_PRESS_S
and poll_button()/ButtonState below.

Low power: the main-loop tick uses machine.lightsleep() instead of a plain
time.sleep() whenever the Wi-Fi radio is off (wifi.radio_active()), which is
almost always -- see wifi.TimeSync's low-power note; the radio itself is
only powered on for the few seconds/minutes around each 4h sync. The idle
tick (MODE_CLOCK, no button held) is bounded at config.IDLE_LIGHTSLEEP_S
rather than sleeping until the next minute -- a button press can't wake a
timed lightsleep() early on rp2 (see docs/low-power.md), so responsiveness
comes from keeping that bound short, not from an interrupt.

Heartbeat: the onboard LED ("LED" pin -- on a *_W board this is wired
through the CYW43 wireless chip, not a plain GPIO, but works fine even with
Wi-Fi off, confirmed live: toggling it after wlan.active(False) still
worked) blinks at config.HEARTBEAT_HZ in every mode, as a simple "the board
is powered and the loop hasn't hung" indicator. Implemented as a genuine
wall-clock toggle (every 1000/(HEARTBEAT_HZ*2) ms) rather than "toggle every
other loop iteration" -- the loop's own iteration rate already varies by
mode (20ms active / 250ms idle, see above), so counting iterations wouldn't
give a consistent, mode-independent Hz.
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

    led = machine.Pin("LED", machine.Pin.OUT)  # onboard LED, see module docstring
    led_on = False
    last_led_toggle_ticks = time.ticks_ms()
    heartbeat_toggle_ms = int(1000 / (config.HEARTBEAT_HZ * 2))

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

    def c_long():
        if alarm.mode == MODE_CLOCK:
            alarm.toggle_enabled()
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
        poll_button(state_c, short_press_cb=c_short, long_press_cb=c_long,
                    long_press_s=config.ALARM_LONG_PRESS_S)

        # Power-on heartbeat: see module docstring for why this is wall-clock
        # timed rather than toggled once per loop iteration.
        if time.ticks_diff(time.ticks_ms(), last_led_toggle_ticks) >= heartbeat_toggle_ms:
            led_on = not led_on
            led.value(led_on)
            last_led_toggle_ticks = time.ticks_ms()

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
                # alarm.enabled is part of the key so long-press-C (which
                # doesn't touch the clock/date) still forces an immediate redraw.
                minute_key = (year, month, day, hour, minute, alarm.enabled)
                if minute_key != last_drawn_minute_key:
                    display.show_clock(hour, minute, year, month, day, alarm_enabled=alarm.enabled)
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

        # Low power: lightsleep() halts the CPU instead of busy-waiting. Two
        # further notes, see docs/low-power.md for the full detail:
        #  - it's best avoided while the Wi-Fi radio is mid-connection on
        #    some rp2 W-board firmware, so fall back to a plain sleep then
        #    (wifi.radio_active() is only True for the brief sync bursts).
        #  - a button press does NOT wake a timed lightsleep() early on rp2
        #    (its GPIO clock is gated off during the sleep) -- so instead of
        #    "sleep until next minute, interrupted by a button", idle ticks
        #    are just bounded short enough (IDLE_LIGHTSLEEP_S) that a press
        #    is always caught on the next wake regardless.
        any_button_held = button_a.value() == 0 or button_b.value() == 0 or button_c.value() == 0
        if alarm.mode == MODE_CLOCK and not any_button_held:
            tick_ms = int(config.IDLE_LIGHTSLEEP_S * 1000)
        else:
            tick_ms = int(config.MAIN_LOOP_TICK_S * 1000)

        if wifi.radio_active():
            time.sleep_ms(int(config.MAIN_LOOP_TICK_S * 1000))
        else:
            machine.lightsleep(tick_ms)


if __name__ == "__main__":
    main()
