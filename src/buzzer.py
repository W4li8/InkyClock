"""
buzzer.py -- passive piezo buzzer interface (PWM-driven).

Wired up as of 2026-09-27 (piezo on pins.BUZZER / GP22 <-> GND), confirmed
with test/test_buzzer.py. play_alarm_tune() still plays only a placeholder
two-tone chime -- fill in a real tune there when you want one; main.py needs
no changes either way.

Wiring / active-vs-passive background: docs/buzzer-notes.md
Bridge-tied (louder, 2-pin) option: pins.BUZZER_BRIDGE_A / _BRIDGE_B, not
wired into this class yet -- see docs/buzzer-notes.md for the technique.
"""

import time
from machine import Pin, PWM

import pins

BUZZER_CONNECTED = True  # piezo is wired to pins.BUZZER -- flip back to False if unplugged


class PassiveBuzzer:
    def __init__(self, gpio=pins.BUZZER):
        self.gpio = gpio
        self._pwm = None
        if BUZZER_CONNECTED:
            self._pwm = PWM(Pin(gpio))
            self._pwm.duty_u16(0)

    def tone(self, freq, ms, volume=0.3):
        """Play a single tone for `ms` milliseconds (blocking). No-op if not connected."""
        if self._pwm is None:
            return
        self._pwm.freq(freq)
        self._pwm.duty_u16(int(65535 * volume / 2))
        time.sleep_ms(ms)
        self._pwm.duty_u16(0)

    def silence(self):
        if self._pwm is not None:
            self._pwm.duty_u16(0)

    def play_alarm_tune(self):
        """
        Call repeatedly while ringing (main.py's MODE_RINGING loop calls this
        once per tick) so the tune plays on repeat.

        TODO: real tune -- replace the placeholder body below once the
        buzzer is wired up. Until BUZZER_CONNECTED is True this only prints
        once per call, so it never blocks the ring loop's button polling.

        NOTE for later: real tone() calls block for their duration, and the
        ring loop also needs to stay responsive to a dismiss press. Once you
        have a real multi-note tune, consider breaking it into short notes
        (<=100ms) so a button check still lands between them, rather than
        one long blocking sequence -- see todo.txt.
        """
        if not BUZZER_CONNECTED:
            print("[buzzer] (not connected) would be sounding the alarm tune now")
            return
        # TODO: real tune -- placeholder two-tone chime
        self.tone(784, 150)
        self.tone(1047, 250)

    def deinit(self):
        if self._pwm is not None:
            self._pwm.deinit()
            self._pwm = None
