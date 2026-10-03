"""
test/test_buzzer.py -- HARDWARE TEST: passive piezo buzzer.

Run against the connected board (no need to copy it there first):
    mpremote connect <port> run test/test_buzzer.py

This drives the piezo through a few audible patterns -- there's no way to
verify sound from software, so read the printed steps and listen. If you
hear nothing: check buzzer.WIRING_MODE matches how it's actually wired
(see buzzer.py's module docstring for the two modes), check the wiring
itself (docs/pico-inky-pack.md for which physical pin GP22 actually is --
it's NOT physical pin 22), and check buzzer.BUZZER_CONNECTED is True.
"""
import time

from buzzer import PassiveBuzzer, BUZZER_CONNECTED, WIRING_MODE, QUIET, LOUD
import pins

print("=== test_buzzer ===")
print(f"WIRING_MODE = {WIRING_MODE!r}")
if WIRING_MODE == "bridge":
    print(f"pins.BUZZER_BRIDGE_A/B = GP{pins.BUZZER_BRIDGE_A}/GP{pins.BUZZER_BRIDGE_B}")
else:
    print(f"pins.BUZZER = GP{pins.BUZZER}")

if not BUZZER_CONNECTED:
    print("FAIL: buzzer.BUZZER_CONNECTED is False in src/buzzer.py -- nothing will sound.")
else:
    buzz = PassiveBuzzer()

    print("Step 1: three distinct rising tones (A4, A5, A6)...")
    for freq, ms in ((440, 300), (880, 300), (1760, 300)):
        print(f"  {freq} Hz for {ms} ms")
        buzz.tone(freq, ms, volume=0.5)
        time.sleep_ms(150)

    print("Step 2: a 200 Hz -> 2000 Hz sweep...")
    f = 200
    while f < 2000:
        buzz.tone(f, 15, volume=0.4)
        f += 40

    print("Step 3: set_tier() sanity check...")
    if WIRING_MODE != "bridge":
        print(f"  WIRING_MODE is {WIRING_MODE!r}, not 'bridge' -- set_tier() should be a no-op.")
        buzz.set_tier(LOUD)
        ok = buzz._bridged is False and buzz._pwm_b is None
        print("  PASS: no-op confirmed (no pwm_b created)" if ok else "  FAIL: set_tier() did something in single mode")
    else:
        print("  WIRING_MODE is 'bridge' -- expect QUIET tone, then a louder LOUD tone")
        buzz.set_tier(QUIET)
        buzz.tone(880, 400, volume=0.5)
        time.sleep_ms(200)
        buzz.set_tier(LOUD)
        buzz.tone(880, 400, volume=0.5)
        buzz.set_tier(QUIET)

    buzz.deinit()
    print("Done. Expected: 3 rising beeps, then a rising sweep, both audible.")
    print("If freq changed but pitch didn't (or nothing happened at all): see")
    print("docs/buzzer-notes.md active-vs-passive section and re-check wiring.")
