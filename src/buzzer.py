"""
buzzer.py -- passive piezo buzzer interface (PWM-driven).

Two wiring modes, selected by WIRING_MODE below -- see docs/buzzer-notes.md
for the diagrams/electrical background of each. Switching WIRING_MODE is
NOT just a software flag -- it requires physically moving the piezo's
leads to match, see the mode descriptions.

  "single" (the ACTUAL current physical wiring, as of 2026-09-27): piezo
  across pins.BUZZER (GP22) <-> GND. One PWM pin. Continuous volume via
  tone()'s `volume` (duty cycle) only -- no hardware loud/quiet tier
  without a second pin.

  "bridge": piezo floating across pins.BUZZER_BRIDGE_A/_B (GP8/GP9), no
  GND connection at all. Adds two hardware volume TIERS on top of the same
  continuous duty-cycle control (set_tier(QUIET) / set_tier(LOUD)):
    - QUIET: only BRIDGE_A carries PWM, BRIDGE_B is held a fixed digital
      low -- same ~3.3V swing as "single" mode, same loudness.
    - LOUD: both pins driven in antiphase (BRIDGE_A normal, BRIDGE_B
      invert=True) -- ~2x voltage swing (+6dB), hardware-synchronized
      since both pins share one PWM slice/counter -- see docs/buzzer-notes.md
      for why that pairing specifically (not just "any two pins") is what
      makes this phase-locked without any software timing tricks.

Now "bridge" -- piezo re-soldered to GP8/GP9 as of 2026-10-02 (was "single"
on GP22/GND before that, see git history if reverting).

play_alarm_tune() still plays only a placeholder two-tone chime -- fill in
a real tune there when you want one; main.py needs no changes either way.
set_tier() is a no-op in "single" mode (nothing to switch to), so it's
always safe to call regardless of which wiring is currently in use.

CLASSIC_VOLUME macro (below): tone()'s `volume` ramp was confirmed live to
be barely audible with the classic (straight duty-cycle) implementation --
expected, not a bug: a bare piezo responds to the SQUARE WAVE'S EDGES (each
transition is the same full voltage swing no matter the duty cycle), so
sweeping duty_u16 mostly changes timbre, not loudness. The two hardware
TIERS above are a real, confirmed-audible volume difference (an actual
voltage-swing change); within a tier, _tone_advanced() below gets a real
loudness ramp instead by gating the tone on/off in short bursts (true
amplitude modulation -- less total acoustic energy at low `volume`, not
just a different-shaped cycle) at the cost of a mild tremolo/buzz character
at low volumes, since the gate rate is in the low-hundreds-of-Hz range, not
far enough above the tone's own frequency to sound perfectly smooth.
CLASSIC_VOLUME=True uses the simple (silent-ramp) original behavior;
False (the current setting) uses the gated one.
"""

import time
from machine import Pin, PWM

import pins

BUZZER_CONNECTED = True   # piezo is physically wired up at all -- flip to False if unplugged
WIRING_MODE = "bridge"    # "single" (pins.BUZZER/GND) or "bridge" (pins.BUZZER_BRIDGE_A/_B) -- see module docstring
CLASSIC_VOLUME = False    # True -> plain duty-cycle tone() (weak volume ramp); False -> gated/bursted tone() (real ramp, some tremolo) -- see module docstring

QUIET = "quiet"
LOUD = "loud"

GATE_WINDOW_MS = 20       # _tone_advanced()'s burst period -- shorter = smoother-sounding ramp but
                          # more PWM churn; longer = more audible as a distinct tremolo/buzz


class PassiveBuzzer:
    def __init__(self):
        self._pwm_a = None
        self._pwm_b = None       # only non-None in "bridge" mode, and only while tier == LOUD
        self._bridged = False    # True == currently driving both pins antiphase (LOUD tier)
        if not BUZZER_CONNECTED:
            return

        if WIRING_MODE == "bridge":
            self._pwm_a = PWM(Pin(pins.BUZZER_BRIDGE_A))
            self._pwm_a.duty_u16(0)
            # Start at QUIET: B held a plain digital low (not PWM), so the
            # piezo sees the same single-ended swing as "single" mode would.
            Pin(pins.BUZZER_BRIDGE_B, Pin.OUT).value(0)
        else:
            self._pwm_a = PWM(Pin(pins.BUZZER))
            self._pwm_a.duty_u16(0)

    def set_tier(self, tier):
        """
        Switch the hardware volume tier (QUIET or LOUD). No-op in "single"
        wiring mode -- there's only one pin, nothing to bridge. Safe to
        call any time, including mid-silence between tone() calls; a tier
        switch reconfigures GP(pins.BUZZER_BRIDGE_B) between a plain
        digital-low output and an inverted PWM output, so it costs a
        PWM.deinit()/re-init, not just a flag flip.
        """
        if self._pwm_a is None or WIRING_MODE != "bridge":
            return
        want_bridged = tier == LOUD
        if want_bridged == self._bridged:
            return
        if want_bridged:
            self._pwm_b = PWM(Pin(pins.BUZZER_BRIDGE_B), invert=True)
            self._pwm_b.duty_u16(0)
        else:
            self._pwm_b.deinit()
            self._pwm_b = None
            Pin(pins.BUZZER_BRIDGE_B, Pin.OUT).value(0)
        self._bridged = want_bridged
        print(f"[buzzer] tier -> {tier}")

    def tone(self, freq, ms, volume=0.3):
        """
        Play a single tone for `ms` milliseconds (blocking). No-op if not
        connected. Dispatches to _tone_classic() or _tone_advanced() per
        the CLASSIC_VOLUME macro -- see module docstring for why they
        sound different (straight duty cycle vs. gated bursts).
        """
        if self._pwm_a is None:
            print(f"[buzzer] tone {freq}Hz {ms}ms (not connected, no-op)")
            return
        if CLASSIC_VOLUME:
            self._tone_classic(freq, ms, volume)
        else:
            self._tone_advanced(freq, ms, volume)

    def _tone_classic(self, freq, ms, volume):
        """Original implementation: one straight duty-cycle PWM tone for
        the full duration. Simple, but see module docstring -- the `volume`
        ramp is weak on a bare piezo this way."""
        pwms = (self._pwm_a, self._pwm_b) if self._bridged else (self._pwm_a,)
        tier = LOUD if self._bridged else QUIET
        print(f"[buzzer] ON  {freq}Hz {ms}ms vol={volume} tier={tier} (classic)")
        duty = int(65535 * volume / 2)
        for p in pwms:
            p.freq(freq)
            p.duty_u16(duty)
        time.sleep_ms(ms)
        for p in pwms:
            p.duty_u16(0)
        print("[buzzer] OFF")

    def _tone_advanced(self, freq, ms, volume):
        """
        Real perceived-loudness ramp via amplitude gating: within each
        GATE_WINDOW_MS window, the tone is held at a fixed "loudest" 50%
        duty cycle for `volume` fraction of the window and silenced for the
        rest, repeated until `ms` has elapsed -- less total acoustic energy
        at low `volume`, which is what actually sounds quieter on a piezo
        (see module docstring for why plain duty-cycle modulation doesn't).
        volume=1.0 is gapless (on for the whole window each time), same as
        a continuous tone; low volume sounds like a fast, buzzy pulse train
        rather than a smooth quiet tone -- an inherent trait of gating a
        piezo this way, not a bug to chase out.
        """
        pwms = (self._pwm_a, self._pwm_b) if self._bridged else (self._pwm_a,)
        tier = LOUD if self._bridged else QUIET
        print(f"[buzzer] ON  {freq}Hz {ms}ms vol={volume} tier={tier} (advanced/gated)")
        full_duty = int(65535 * 0.5 / 2)  # the fixed "loudest" duty per burst; volume controls gating, not this
        for p in pwms:
            p.freq(freq)

        on_ms = max(1, int(GATE_WINDOW_MS * volume))
        off_ms = GATE_WINDOW_MS - on_ms
        elapsed = 0
        while elapsed < ms:
            for p in pwms:
                p.duty_u16(full_duty)
            time.sleep_ms(min(on_ms, ms - elapsed))
            for p in pwms:
                p.duty_u16(0)
            if off_ms > 0:
                time.sleep_ms(off_ms)
            elapsed += GATE_WINDOW_MS
        print("[buzzer] OFF")

    def silence(self):
        if self._pwm_a is not None:
            print("[buzzer] silence()")
            self._pwm_a.duty_u16(0)
            if self._pwm_b is not None:
                self._pwm_b.duty_u16(0)

    def play_alarm_tune(self):
        """
        Call repeatedly while ringing (main.py's MODE_RINGING loop calls this
        once per tick) so the tune plays on repeat.

        TODO: real tune -- replace the placeholder body below once the
        buzzer is wired up. Until BUZZER_CONNECTED is True this only prints
        once per call, so it never blocks the ring loop's button polling.

        TODO: escalation idea (needs WIRING_MODE == "bridge" wired up
        first) -- track how long MODE_RINGING has been active (e.g. a
        timestamp passed in, or main.py calling set_tier(LOUD) itself once
        some threshold passes) and call self.set_tier(LOUD) partway through
        an unanswered alarm, having started at QUIET. Not implemented here:
        that's main.py/alarm.py ring-state logic, out of scope for this
        file, which only exposes the tier capability.

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
        if self._pwm_a is not None:
            self._pwm_a.deinit()
            self._pwm_a = None
        if self._pwm_b is not None:
            self._pwm_b.deinit()
            self._pwm_b = None
