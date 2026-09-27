# Pico 2 W Debug Port (SWD) — What It Is and Isn't

Source: [Pico 2 W Datasheet](https://datasheets.raspberrypi.com/picow/pico-2-w-datasheet.pdf) §3.9 "Debugging", confirmed against the pinout diagram at [`assets/pico2w_pin_functions-05.png`](assets/pico2w_pin_functions-05.png).

## What it is

A dedicated 3-pin header, separate from the 40-pin GPIO header, breaking out the RP2350's Arm Serial Wire Debug (SWD) interface:

| Pin | Signal |
|---|---|
| 1 | SWCLK |
| 2 | GND |
| 3 | SWDIO |

> "Pico 2 W brings the RP2350 serial wire debug (SWD) interface to a three-pin debug header... The RP2350 chip has internal pull-up resistors on the SWDIO and SWCLK pins, both nominally 60 kΩ." — datasheet §3.9

## Why it can't drive a buzzer (or anything else GPIO-ish)

SWCLK/SWDIO connect directly to dedicated debug logic baked into the RP2350 silicon — they are **not muxed to any GPIO pad function**. There is no `machine.Pin`/`PWM` binding for them in MicroPython or CircuitPython; the debug block doesn't expose a PWM peripheral either, so even direct register-level access wouldn't get you a usable tone signal.

## What it's actually for on this project

Attach a second Pico flashed with [Picoprobe](https://github.com/raspberrypi/picoprobe) firmware (SWCLK/GND/SWDIO + power) to get real hardware debugging via OpenOCD — breakpoints, single-stepping, live variable inspection — for the alarm-trigger / RTC / wifi logic once `print()`-debugging over USB serial stops being enough. Not a path to sound.

For sound, use a normal GPIO pad on the 40-pin header — see [`buzzer-notes.md`](buzzer-notes.md), recommended pin **GP22**.
