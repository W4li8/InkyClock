"""
test/test_buzzer.py -- HARDWARE TEST: passive piezo buzzer (pins.BUZZER / GP22).

Run against the connected board (no need to copy it there first):
    mpremote connect <port> run test/test_buzzer.py

This drives the piezo through a few audible patterns -- there's no way to
verify sound from software, so read the printed steps and listen. If you
hear nothing: check the wiring (GP22 <-> piezo <-> GND, see
docs/pico-inky-pack.md for which physical pin GP22 actually is -- it's NOT
physical pin 22), and check buzzer.BUZZER_CONNECTED is True in src/buzzer.py.
"""
import time

from buzzer import PassiveBuzzer, BUZZER_CONNECTED
import pins

print("=== test_buzzer ===")
print("pins.BUZZER = GP{}".format(pins.BUZZER))

if not BUZZER_CONNECTED:
    print("FAIL: buzzer.BUZZER_CONNECTED is False in src/buzzer.py -- nothing will sound.")
else:
    buzz = PassiveBuzzer()

    print("Step 1: three distinct rising tones (A4, A5, A6)...")
    for freq, ms in ((440, 300), (880, 300), (1760, 300)):
        print("  {} Hz for {} ms".format(freq, ms))
        buzz.tone(freq, ms, volume=0.5)
        time.sleep_ms(150)

    print("Step 2: a 200 Hz -> 2000 Hz sweep...")
    f = 200
    while f < 2000:
        buzz.tone(f, 15, volume=0.4)
        f += 40

    buzz.deinit()
    print("Done. Expected: 3 rising beeps, then a rising sweep, both audible.")
    print("If freq changed but pitch didn't (or nothing happened at all): see")
    print("docs/buzzer-notes.md active-vs-passive section and re-check wiring.")
