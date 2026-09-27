"""
main.py -- InkyClock entry point: button polling, mode dispatch, main loop.

Flow: boot -> show a status message -> block once on wifi.TimeSync.sync_blocking()
so the clock is right immediately -> loop forever polling buttons, the RTC,
and (non-blocking) the 4h resync schedule via wifi.TimeSync.poll().

Button behaviour (see alarm.py for the state machine these call into):
  - short A            : while MODE_EDIT, +1 on the selected digit.
                         while MODE_RINGING, dismiss.
  - short B            : while MODE_EDIT, cycle to the next digit
                          (0->1->2->3->0->..., never auto-exits -- see below
                          for how you actually leave). While MODE_RINGING, dismiss.
  - long B (3s)         : toggles MODE_CLOCK <-> MODE_EDIT (enter_edit() /
                          exit_edit()). While MODE_RINGING, dismiss instead.
  - (MODE_EDIT also auto-exits after config.ALARM_EDIT_TIMEOUT_S of no A/B/C
     activity -- alarm.edit_idle_expired(), polled below.)
  - press C (any length): from MODE_CLOCK, shows the alarm time for
                          config.ALARM_LONG_PRESS_S seconds regardless of
                          hold duration (MODE_PREVIEW, c_press/preview_expired).
                          During MODE_EDIT instead, short C is -1 on the
                          selected digit (adjust_digit(-1), same as short A's
                          +1, just the other direction).
                          While MODE_RINGING, dismiss.
  - long C (3s)         : if the press is held for the full preview window
                          (MODE_CLOCK or MODE_PREVIEW), also toggles the
                          alarm on/off (alarm.toggle_enabled(); shown via the
                          preview's "ALARM -- ON/OFF" label and MODE_CLOCK's
                          "ALARM OFF" corner tag). While MODE_RINGING, dismiss.

To change what "short" vs "long" press means, see config.ALARM_LONG_PRESS_S
and poll_button()/ButtonState below.

Low power: the main-loop tick is a plain time.sleep_ms(), deliberately NOT
machine.lightsleep() -- confirmed live (isolated, reproducible test) that
lightsleep() freezes machine.RTC() for its entire duration on this board/
firmware, which silently broke the clock every time MODE_CLOCK went idle
(that idle path spends nearly all its time asleep by design). This was the
root cause of this session's recurring "clock stopped" reports, not a
fluke -- see docs/low-power.md for the full story and why the earlier
lightsleep-based design seemed to work in short tests. The idle tick
(MODE_CLOCK, no button held) is still bounded at config.IDLE_TICK_S rather
than sleeping until the next minute, now purely so a button press is
picked up promptly, not for any lightsleep-wake reason. The Wi-Fi-radio-off
power saving (wifi.TimeSync's low-power note) is untouched by any of this
and remains the real power win.

Heartbeat: the onboard LED ("LED" pin -- on a *_W board this is wired
through the CYW43 wireless chip, not a plain GPIO, but works fine even with
Wi-Fi off, confirmed live: toggling it after wlan.active(False) still
worked) blinks in every mode as a "the board is powered and the loop hasn't
hung" indicator, and doubles as a Wi-Fi status light: config.HEARTBEAT_WIFI_HZ
(fast) while wifi.radio_active(), config.HEARTBEAT_IDLE_HZ (slow) otherwise.
Implemented as a genuine wall-clock toggle rather than "toggle every other
loop iteration" -- the loop's own iteration rate already varies by mode
(20ms active / 250ms idle, see above), so counting iterations wouldn't give
a consistent Hz independent of that.
"""

import time
import machine

import config
import pins
import wifi
from display import InkyDisplay
from buzzer import PassiveBuzzer
from alarm import Alarm, MODE_CLOCK, MODE_EDIT, MODE_RINGING, MODE_PREVIEW


class ButtonState:
    """Debounced press tracking for one pin, active-low with a pull-up."""

    def __init__(self, pin):
        self.pin = pin
        self.was_pressed = False
        self.press_start_ticks = None
        self.long_press_fired = False


def poll_button(state, press_cb=None, short_press_cb=None, long_press_cb=None, long_press_s=None):
    """Call once per main-loop tick per button. Fires press_cb immediately
    on the press edge, short_press_cb on release (unless a long press
    already fired), long_press_cb once as soon as the hold crosses
    long_press_s."""
    pressed = state.pin.value() == 0
    now = time.ticks_ms()

    if pressed and not state.was_pressed:
        state.press_start_ticks = now
        state.long_press_fired = False
        if press_cb:
            press_cb()

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

    def a_short():
        print(f"[main] button A short (mode={alarm.mode})")
        if alarm.mode == MODE_EDIT:
            alarm.adjust_digit(+1)
        elif alarm.mode == MODE_RINGING:
            alarm.stop_ringing()
            buzzer.silence()

    def b_short():
        print(f"[main] button B short (mode={alarm.mode})")
        if alarm.mode == MODE_EDIT:
            alarm.next_digit()
        elif alarm.mode == MODE_RINGING:
            alarm.stop_ringing()
            buzzer.silence()

    def b_long():
        print(f"[main] button B LONG (mode={alarm.mode})")
        if alarm.mode == MODE_CLOCK:
            alarm.enter_edit()
        elif alarm.mode == MODE_EDIT:
            alarm.exit_edit()
        elif alarm.mode == MODE_RINGING:
            alarm.stop_ringing()
            buzzer.silence()

    def c_press():
        # Fires immediately on press, before we know if it'll be short or
        # long -- start_preview() shows the alarm time regardless; c_long()
        # below additionally toggles enabled if the hold reaches the full
        # config.ALARM_LONG_PRESS_S window.
        print(f"[main] button C pressed (mode={alarm.mode})")
        if alarm.mode == MODE_CLOCK:
            alarm.start_preview()

    def c_short():
        print(f"[main] button C released short (mode={alarm.mode})")
        if alarm.mode == MODE_EDIT:
            alarm.adjust_digit(-1)
        elif alarm.mode == MODE_RINGING:
            alarm.stop_ringing()
            buzzer.silence()

    def c_long():
        print(f"[main] button C LONG (mode={alarm.mode})")
        if alarm.mode in (MODE_CLOCK, MODE_PREVIEW):
            alarm.toggle_enabled()
        elif alarm.mode == MODE_RINGING:
            alarm.stop_ringing()
            buzzer.silence()

    print("[main] InkyClock booting")

    # Boot-time sync: block once so the clock is correct right away, instead
    # of waiting for the next scheduled 4h slot (see wifi.TimeSync docstring).
    display.show_message("Syncing time...")
    display.push_if_due()  # main loop isn't running yet to do this for us
    time_sync.sync_blocking()

    print("[main] boot sync done, entering main loop")
    last_mode = alarm.mode
    last_drawn_minute_key = None   # (y, mo, d, hh, mm) last shown in MODE_CLOCK
    last_edit_state = None         # (hour, minute, digit_index) last shown in MODE_EDIT
    last_preview_state = None      # (hour, minute, enabled) last shown in MODE_PREVIEW
    border_visible = True
    last_border_toggle_ticks = time.ticks_ms()

    while True:
        poll_button(state_a, short_press_cb=a_short)
        poll_button(state_b, short_press_cb=b_short, long_press_cb=b_long,
                    long_press_s=config.ALARM_LONG_PRESS_S)
        poll_button(state_c, press_cb=c_press, short_press_cb=c_short, long_press_cb=c_long,
                    long_press_s=config.ALARM_LONG_PRESS_S)

        # Power-on heartbeat / Wi-Fi status light: see module docstring for
        # why this is wall-clock timed rather than toggled per loop iteration.
        heartbeat_hz = config.HEARTBEAT_WIFI_HZ if wifi.radio_active() else config.HEARTBEAT_IDLE_HZ
        heartbeat_toggle_ms = int(1000 / (heartbeat_hz * 2))
        if time.ticks_diff(time.ticks_ms(), last_led_toggle_ticks) >= heartbeat_toggle_ms:
            led_on = not led_on
            led.value(led_on)
            last_led_toggle_ticks = time.ticks_ms()

        # Force a redraw on any mode transition, so we never leave a stale
        # view (e.g. the alarm editor) on screen after switching modes.
        if alarm.mode != last_mode:
            print(f"[main] mode: {last_mode} -> {alarm.mode}")
            last_drawn_minute_key = None
            last_edit_state = None
            last_preview_state = None
            last_mode = alarm.mode
            if alarm.mode == MODE_RINGING:
                border_visible = True
                last_border_toggle_ticks = time.ticks_ms()

        # Don't let a resync attempt's HTTP call delay the ring itself.
        if alarm.mode != MODE_RINGING:
            time_sync.poll()

        year, month, day, weekday, hour, minute, second, _sub = rtc.datetime()

        if alarm.mode == MODE_CLOCK:
            if alarm.check_ring((year, month, day, hour, minute, second)):
                alarm.start_ringing()
            else:
                # alarm.enabled is part of the key so long-press-C (which
                # doesn't touch the clock/date) still forces an immediate redraw.
                minute_key = (year, month, day, hour, minute, alarm.enabled)
                if minute_key != last_drawn_minute_key:
                    display.show_clock(hour, minute, year, month, day, weekday=weekday, alarm_enabled=alarm.enabled)
                    last_drawn_minute_key = minute_key

        elif alarm.mode == MODE_EDIT:
            if alarm.edit_idle_expired():
                alarm.exit_edit()
            else:
                edit_state = (alarm.hour, alarm.minute, alarm.digit_index)
                if edit_state != last_edit_state:
                    display.show_alarm_edit(*edit_state)
                    last_edit_state = edit_state

        elif alarm.mode == MODE_PREVIEW:
            if alarm.preview_expired():
                alarm.end_preview()
            else:
                preview_state = (alarm.hour, alarm.minute, alarm.enabled)
                if preview_state != last_preview_state:
                    display.show_alarm_preview(*preview_state)
                    last_preview_state = preview_state

        elif alarm.mode == MODE_RINGING:
            buzzer.play_alarm_tune()
            now_ms = time.ticks_ms()
            half_period_ms = int(1000 / config.ALARM_RING_FLASH_HZ / 2)
            if time.ticks_diff(now_ms, last_border_toggle_ticks) >= half_period_ms:
                border_visible = not border_visible
                last_border_toggle_ticks = now_ms
                display.flash_alarm_border(alarm.hour, alarm.minute, border_visible)

        # Non-blocking: only actually touches hardware (and only then
        # blocks, for that single real push) if something was drawn above
        # AND the panel's throttle window has elapsed -- see its docstring
        # for why the previous design (blocking inside every view method)
        # was a real bug, not just inefficient.
        display.push_if_due()

        # NOT machine.lightsleep() -- confirmed live (isolated, reproducible,
        # 200 iterations) that it freezes machine.RTC() completely on this
        # board/firmware for the whole sleep duration. Since MODE_CLOCK's
        # idle path spends nearly all its time in this call, that silently
        # broke the clock every single time it went idle -- the root cause
        # of this session's recurring "clock stopped" reports, not a fluke.
        # time.ticks_ms() DOES survive lightsleep correctly (confirmed:
        # 2503ms measured for 10x250ms), so it stays trustworthy for
        # anything timing-based in this file; machine.RTC() does not survive
        # lightsleep, which is exactly what broke. time.sleep_ms() has none
        # of this: it doesn't touch clock gating, only the CPU's own wait
        # state, so RTC keeps ticking normally through it. Full story:
        # docs/low-power.md.
        any_button_held = button_a.value() == 0 or button_b.value() == 0 or button_c.value() == 0
        if alarm.mode == MODE_CLOCK and not any_button_held:
            tick_ms = int(config.IDLE_TICK_S * 1000)
        else:
            tick_ms = int(config.MAIN_LOOP_TICK_S * 1000)

        time.sleep_ms(tick_ms)


if __name__ == "__main__":
    main()
