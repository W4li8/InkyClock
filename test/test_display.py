"""
test/test_display.py -- HARDWARE TEST: Pico Inky Pack e-ink display.

Run against the connected board:
    mpremote connect <port> run test/test_display.py

Each step below is human-verified -- look at the actual screen after it
prints; there's no way to check pixel content from here.
"""
import time

from display import InkyDisplay

print("=== test_display ===")
d = InkyDisplay()
print("Panel size: {}x{}".format(d.width, d.height))

print("Step 1: show_message -- expect 'DISPLAY TEST OK' in the corner")
d.show_message("DISPLAY TEST OK")
time.sleep(2)

print("Step 2: show_clock -- expect a big centered 12:34, 'Fri 02/01/26' below it (bigger date font)")
d.show_clock(12, 34, 2026, 1, 2, weekday=4, alarm_enabled=True)  # 2026-01-02 is a Friday
time.sleep(2)

print("Step 3: show_clock with alarm disabled -- expect an 'ALARM OFF' corner label too")
d.show_clock(12, 34, 2026, 1, 2, weekday=4, alarm_enabled=False)
time.sleep(2)

print("Step 4: show_alarm_edit -- expect 07:00 with the first digit (0) blanked/blinking-style")
d.show_alarm_edit(7, 0, 0, False)
time.sleep(2)

print("Step 5: show_alarm_preview (enabled) -- expect 'ALARM -- ON' + big 07:00")
d.show_alarm_preview(7, 0, True)
time.sleep(2)

print("Step 6: show_alarm_preview (disabled) -- expect 'ALARM -- OFF' + big 07:00")
d.show_alarm_preview(7, 0, False)
time.sleep(2)

print("Step 7: flash_alarm_border x4 -- expect the border to toggle on/off")
for i in range(4):
    d.flash_alarm_border(7, 0, i % 2 == 0)
    time.sleep_ms(400)

print("Done. If any step showed a blank/garbled screen, check docs/low-power.md")
print("isn't relevant here (this test doesn't touch sleep) and re-check the")
print("display's SPI pins (pins.py DISPLAY_*) against docs/pico-inky-pack.md.")
