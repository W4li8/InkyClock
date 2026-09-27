"""
test/test_pins.py -- LOGIC TEST: pins.py has no GPIO collisions.

No hardware needed, but run the same way as the others for consistency:
    mpremote connect <port> run test/test_pins.py

Not a hardware test itself, but the pin map underpins every hardware test
here -- a collision caught by this before flashing anything saves a lot of
"why doesn't the display/buzzer/button work" debugging.
"""
import pins

print("=== test_pins ===")

active = {
    "DISPLAY_CS": pins.DISPLAY_CS,
    "DISPLAY_CLK": pins.DISPLAY_CLK,
    "DISPLAY_MOSI": pins.DISPLAY_MOSI,
    "DISPLAY_DC": pins.DISPLAY_DC,
    "DISPLAY_RESET": pins.DISPLAY_RESET,
    "DISPLAY_BUSY": pins.DISPLAY_BUSY,
    "BUTTON_A": pins.BUTTON_A,
    "BUTTON_B": pins.BUTTON_B,
    "BUTTON_C": pins.BUTTON_C,
    "BUZZER": pins.BUZZER,
    "BUZZER_BRIDGE_A": pins.BUZZER_BRIDGE_A,
    "BUZZER_BRIDGE_B": pins.BUZZER_BRIDGE_B,
}
wireless_reserved = {
    pins.WIRELESS_POWER_ON,
    pins.WIRELESS_SPI_DATA_IRQ,
    pins.WIRELESS_SPI_CS,
    pins.WIRELESS_SPI_CLK_ADC,
}

ok = True

seen = {}
for name, gpio in active.items():
    if gpio in seen:
        ok = False
        print("FAIL: GP{} used by both {} and {}".format(gpio, seen[gpio], name))
    seen[gpio] = name

for name, gpio in active.items():
    if gpio in wireless_reserved:
        ok = False
        print("FAIL: {} = GP{} is wireless-reserved, unusable on a *_W board".format(name, gpio))

bad_free = [p for p in pins.FREE_PINS if p in seen or p in wireless_reserved]
if bad_free:
    ok = False
    print("FAIL: FREE_PINS lists pin(s) that are actually claimed/reserved:", bad_free)

if pins.BUZZER in (pins.BUZZER_BRIDGE_A, pins.BUZZER_BRIDGE_B):
    ok = False
    print("FAIL: BUZZER overlaps a BUZZER_BRIDGE_* pin -- pick one wiring scheme, not both")

print("PASS: no collisions in pins.py" if ok else "test_pins: FAILED, see above")
