# Driving a Buzzer from the Pico 2 W (MicroPython)

## Active vs. passive buzzer

| | Active | Passive |
|---|---|---|
| Inside | Piezo/coil **+ built-in oscillator** | Bare piezo element or coil, no oscillator |
| Drive signal | DC — pin high = beep | Square wave (PWM) at the desired tone frequency |
| Pitch | Fixed, whatever the internal oscillator runs at (~2–4 kHz) | Whatever frequency you drive it at — melodies, chirps, sweeps |
| Code | `Pin(22, Pin.OUT).value(1)` | `PWM(Pin(22))` + `.freq()` + `.duty_u16()` |
| Typical current | 20–40 mA (module usually includes its own transistor) | Piezo: ~1–3 mA, high impedance. Magnetic/coil: 30–80 mA, low impedance |
| How to tell them apart if unlabeled | Apply 3.3 V DC directly — it beeps at a fixed pitch | Apply DC — silent or just a click; needs an oscillating signal to make sound |

**For this alarm clock: use a passive piezo buzzer.** A fixed single-note active buzzer is either quiet enough to sleep through or comes in one harsh volume/pitch — bad for both a gentle wake tone and an escalating "you didn't hit snooze" pattern. A passive buzzer under PWM control lets the same 2 wires do both.

## Wiring

- **Passive piezo** (high impedance): straight across GP22 → GND. Draws a few mA, well within a GPIO's ~12 mA safe limit.
- **Louder without extra parts** — bridge-tied drive across `BUZZER_BRIDGE_A`/`BUZZER_BRIDGE_B` (GP2/GP3) — see [Bridge-tied (BTL) drive](#bridge-tied-btl-drive-for-more-volume) below.
- **Passive magnetic/coil buzzer** (low impedance, 16–42 Ω): needs a transistor (BC337, 2N3904, or small logic-level MOSFET) to switch it, base/gate driven from the GPIO through a resistor, plus a flyback diode (1N4148 or similar) across the coil to protect the transistor.
- **Real audio instead of beeps**: an I2S DAC/amp module (e.g. MAX98357A) — see [I2S amp vs. PWM-on-piezo](#i2s-amp-vs-pwm-on-piezo-for-actual-audio) below.

## `machine.PWM` API (MicroPython, rp2 port)

Source: [MicroPython machine.PWM docs](https://docs.micropython.org/en/latest/library/machine.PWM.html).

```python
machine.PWM(dest, *, freq, duty_u16, duty_ns, invert=False)
```

- `freq([value])` — get/set frequency in Hz
- `duty_u16([value])` — get/set duty cycle, 0–65535 (50% = loudest square wave for a piezo)
- `duty_ns([value])` — get/set pulse width in nanoseconds
- `init(*, freq, duty_u16, duty_ns)` — reconfigure an existing PWM object
- `deinit()` — release the PWM channel (silence + free it for other use)

RP2 specifics: RP2040 has 8 independent PWM slices (2 channels each); RP2350 has 12, but that only matters for chips with more than 32 GPIOs — on the Pico 2 W's 30 header pins, the slice mapping is identical to the RP2040 (`slice = (gpio >> 1) & 7`), so you're still working with 8 usable slices in practice. Two GPIOs sharing a slice can't have independent tones (same counter/frequency) — see the bridge-tied section below for why that's actually useful, not a limitation.

## Minimal single-pin test

```python
from machine import Pin, PWM
import time

buzz = PWM(Pin(22))

def tone(freq, ms, vol=0.3):
    buzz.freq(freq)
    buzz.duty_u16(int(32768 * vol))   # 50% duty = loudest
    time.sleep_ms(ms)
    buzz.duty_u16(0)                  # silence between notes

for _ in range(3):                    # simple two-tone chime: G5, C6
    tone(784, 150)
    tone(1047, 250)
    time.sleep_ms(400)

buzz.deinit()
```

If `vol` changes loudness but `freq()` changes nothing, it's actually an active buzzer wired in (only responds to on/off, not frequency).

## Bridge-tied (BTL) drive, for more volume

The RP2350 (and RP2040) PWM hardware is organized as slices, each with two channels, **A and B, that share the same counter and clock divider** — confirmed straight from the [pico-sdk register layout](https://github.com/raspberrypi/pico-sdk/blob/master/src/rp2350/hardware_structs/include/hardware/structs/pwm.h): one `CC` register per slice holds both channels' compare values (`A` and `B` fields), and one `CSR` register holds independent invert bits per channel (`A_INV`, `B_INV`). Because A and B are driven off the *same* counter, two GPIOs on the same slice are automatically phase-locked in hardware — no software synchronization needed.

That's exactly what a bridge-tied (BTL) buzzer drive wants: put the piezo across two same-slice pins, set one channel's output inverted relative to the other, and the piezo sees roughly double the peak-to-peak voltage swing of a single pin (~+6 dB), for free, with only one extra jumper wire.

**Which GPIOs share a slice:** `slice = (gpio >> 1) & 7`, `channel = gpio & 1` (even = A, odd = B) — so consecutive pin pairs `(0,1)`, `(2,3)`, `(4,5)`, `(6,7)`, `(8,9)`, … are always slice-mates. On this project's free-pin list, **GP2 (slice 1, channel A) + GP3 (slice 1, channel B)** is the cleanest pair: both free, physically adjacent (header pins 4 & 5), a GND sits right next to them at pin 3, and neither collides with the default UART0 console on GP0/GP1. These are `BUZZER_BRIDGE_A`/`BUZZER_BRIDGE_B` in [`src/pins.py`](../src/pins.py).

```python
from machine import Pin, PWM
import time

pwm_a = PWM(Pin(2))                    # BUZZER_BRIDGE_A
pwm_b = PWM(Pin(3), invert=True)       # BUZZER_BRIDGE_B, antiphase

def tone(freq, ms, vol=0.3):
    duty = int(32768 * vol)
    for p in (pwm_a, pwm_b):
        p.freq(freq)
        p.duty_u16(duty)
    time.sleep_ms(ms)
    for p in (pwm_a, pwm_b):
        p.duty_u16(0)

tone(784, 150)
```

Wire the piezo across GP2 and GP3 directly (no GND connection needed for the piezo itself in this mode — it floats between the two driven pins). Only use this **or** the single-pin `BUZZER` (GP22) hookup with a given physical buzzer, not both at once.

## I2S amp vs. PWM-on-piezo, for actual audio

You mentioned already having an I2S amp (e.g. MAX98357A-class board) — worth using it, and here's the honest tradeoff:

**A piezo under plain tone-PWM (as above) is a beeper, not a speaker.** You *can* push it further than single tones — some hobby projects drive a piezo with a fast fixed carrier (tens of kHz) and vary the duty cycle sample-by-sample to approximate real PCM audio (a crude 1-bit DAC, doable on the RP2350 with PWM+DMA). But a piezo disc is a narrow-band resonant transducer tuned for a few-kHz beep: outside that resonance the response is thin and harsh, there's no bass, output is quiet at low/high frequencies, and quality is mono/tinny even in the best case. It's real effort for a result that still sounds like a piezo.

**An I2S DAC/amp is a proper digital audio path**: multi-bit PCM (not a 1-bit approximation), driving a real speaker, so you get actual bass/clarity/intelligible voice — meaning you could use a real recording, a pleasant chime, or gradually-loudening music instead of square-wave beeps. MicroPython's `machine.I2S` is supported on the rp2 port (PIO-based, currently a "Technical Preview," 2 I2S buses available) — see the [MicroPython rp2 quickref](https://docs.micropython.org/en/latest/rp2/quickref.html) and the [`machine_i2s.c` source](https://github.com/micropython/micropython/blob/master/ports/rp2/machine_i2s.c). Typical wiring is 3 GPIOs (BCLK, LRC/WS, DIN) plus power/GND to the amp board, then a speaker on its output — no extra transistor/driver circuitry needed since the amp module handles that.

**Recommendation:** since you already have the I2S amp, use it as the primary alarm sound (real chime/voice/music, adjustable volume in software) and keep the piezo on GP22 as a cheap, code-simple backup/secondary alarm — e.g. a fallback beeper if the I2S path ever fails to init, or a second "did you turn off the main alarm" nag tone. Both can coexist since they're on entirely separate pins.

## Alarm escalation pattern idea

Since this is going into an alarm clock: start with a quiet single tone, and if no button (A/B/C on GP12/13/14) is pressed within N seconds, increase `vol`, shorten the gaps, or switch to a faster/harsher note pattern. `duty_u16` gives volume control for the ramp; `freq` gives you the harsher-tone escalation without extra hardware.
