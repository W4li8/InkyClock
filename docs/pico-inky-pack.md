# Pimoroni Pico Inky Pack — Pins & Buzzer Notes

Product: [Pico Inky Pack](https://shop.pimoroni.com/en-us/products/pico-inky-pack) — 2.9" black/white UC8151 e-paper + 3 tactile buttons, plugs onto the Pico's 40-pin castellated header.

**No audio hardware on board.** It's display + buttons only — any alarm sound needs an external buzzer/speaker wired to a free GPIO.

## Confirmed pin usage

Straight from Pimoroni's own source, [`examples/inky_pack/inky_pack_demo.cpp`](https://github.com/pimoroni/pimoroni-pico/blob/main/examples/inky_pack/inky_pack_demo.cpp) (cross-checked against the MicroPython examples in [`pimoroni-examples/`](pimoroni-examples/) in this repo):

| Function | GPIO |
|---|---|
| Display CS | GP17 |
| Display CLK (SCK) | GP18 |
| Display MOSI | GP19 |
| Display DC | GP20 |
| Display RESET | GP21 |
| Display BUSY | GP26 |
| Button A | GP12 |
| Button B | GP13 |
| Button C | GP14 |

These are the pins the `picographics`/`Button` MicroPython modules actually drive (see `button_test.py` and `clock.py` in `pimoroni-examples/`) — treat them as reserved.

## Pins listed in the source but not necessarily wired on this product

The same C++ enum also defines `D`/`UP` = GP15, `E`/`DOWN` = GP11, `USER` = GP23, `VBUS_DETECT` = GP24, `LED` = GP25, `BATTERY` = GP29, `ENABLE_3V3` = GP10. This enum is shared boilerplate across several Pimoroni Pico+eInk boards (it matches the Badger 2040 pin map almost exactly); the retail Pico Inky Pack is only documented and sold with **3** buttons (A/B/C) plus the standard Pico reset button, so D/E/USER most likely have no physical switch attached on this board.

**Practically:** GP15 and GP11 are very likely free, but if you want zero risk, check for unpopulated pads near the button footprint or just avoid them and use GP22 instead (see below) — nothing about this list changes that recommendation.

Separately: GP23/24/25/29 are moot regardless, because on a **Pico 2 W** those four GPIOs are claimed internally by the CYW43439 wireless chip (see [`pico-2-w-pinout.md`](pico-2-w-pinout.md)) and aren't exposed on the header at all. So even if the Inky Pack's `USER`/`LED`/`BATTERY` pads were physically wired, they wouldn't do anything useful on this specific combination of boards — one more reason not to rely on them.

## Recommended buzzer pin

**GP22** — physical pin 29, right next to a GND (pin 28). It has:
- No role in the display SPI bus or buttons above
- No role in the Pico 2 W's internal wireless wiring
- Its own PWM slice, independent of the display/button pins
- Not an ADC pin (so it doesn't compete with GP26–28 if you ever add a light/battery sensor)

See [`buzzer-notes.md`](buzzer-notes.md) for wiring and active-vs-passive buzzer details, and [`pico-2-w-pinout.md`](pico-2-w-pinout.md) for the full free-pin table.
