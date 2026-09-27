# Raspberry Pi Pico 2 W — GPIO Pinout & Debug Port

Source: [Pico 2 W Datasheet (RP-008304-DS-3)](https://datasheets.raspberrypi.com/picow/pico-2-w-datasheet.pdf), pages 4 & 7. Full PDF cached at [`assets/pico2w_pin_functions-05.png`](assets/pico2w_pin_functions-05.png) (Figure 2, pin functions) and [`assets/pico2w_pin_numbering-08.png`](assets/pico2w_pin_numbering-08.png) (Figure 4, physical numbering).

## Pins reserved for on-board wireless (NOT general GPIO, not on the header)

The Pico 2 W uses an Infineon CYW43439 for 2.4 GHz wireless, wired internally via SPI to four RP2350 GPIOs. These **do not appear on the 40-pin header at all** — physical pin 29 jumps straight from `GP22` to `RUN` (pin 30):

| GPIO | Internal function |
|---|---|
| GP23 | Wireless power-on signal |
| GP24 | Wireless SPI data / IRQ |
| GP25 | Wireless SPI CS (also gates GP29 ADC read of VSYS) |
| GP29 | Wireless SPI CLK, or ADC3 to measure VSYS/3 |

There's also a separate `WL_GPIO0` (on-board LED), `WL_GPIO1` (SMPS power-save), `WL_GPIO2` (VBUS sense) — these live on the wireless chip itself, not the RP2350, and aren't accessible as normal `machine.Pin`s either.

**Practical effect:** on a Pico 2 W (unlike a plain Pico 2), GP23/24/25/29 are simply absent from your usable pin set.

## Debug port (SWD) — not usable as GPIO

Confirmed straight from the datasheet (§3.9 Debugging):

> Pico 2 W brings the RP2350 serial wire debug (SWD) interface to a three-pin debug header... The RP2350 chip has internal pull-up resistors on the SWDIO and SWCLK pins, both nominally 60 kΩ.

The 3-pin `DEBUG` header (bottom of the board, separate from the 40-pin header) is:

| Pin | Signal |
|---|---|
| 1 | SWCLK |
| 2 | GND |
| 3 | SWDIO |

This connects directly to dedicated debug silicon on the RP2350 — it is **not muxed to any GPIO pad**, so it cannot be repurposed to drive a buzzer or anything else via `machine.Pin`/`PWM`. Its actual use: connect a second Pico running [Picoprobe](https://github.com/raspberrypi/picoprobe) + OpenOCD to get real breakpoint/step debugging of this project's firmware.

## Full pin-function table (from Figure 2)

| Physical pin | GPIO | Default functions available |
|---|---|---|
| 1 | GP0 | UART0 TX, I2C0 SDA, SPI0 RX |
| 2 | GP1 | UART0 RX, I2C0 SCL, SPI0 CSn |
| 3 | GND | — |
| 4 | GP2 | I2C1 SDA, SPI0 SCK |
| 5 | GP3 | I2C1 SCL, SPI0 TX |
| 6 | GP4 | UART1 TX, I2C0 SDA, SPI0 RX |
| 7 | GP5 | UART1 RX, I2C0 SCL, SPI0 CSn |
| 8 | GND | — |
| 9 | GP6 | I2C1 SDA, SPI0 SCK |
| 10 | GP7 | I2C1 SCL, SPI0 TX |
| 11 | GP8 | UART1 TX, I2C0 SDA, SPI1 RX |
| 12 | GP9 | UART1 RX, I2C0 SCL, SPI1 CSn |
| 13 | GND | — |
| 14 | GP10 | I2C1 SDA, SPI1 SCK |
| 15 | GP11 | I2C1 SCL, SPI1 TX |
| 16 | GP12 | UART0 TX, I2C0 SDA, SPI1 RX |
| 17 | GP13 | UART0 RX, I2C0 SCL, SPI1 CSn |
| 18 | GND | — |
| 19 | GP14 | I2C1 SDA, SPI1 SCK |
| 20 | GP15 | I2C1 SCL, SPI1 TX |
| 21 | GP16 | SPI0 RX, I2C0 SDA, UART0 TX |
| 22 | GP17 | SPI0 CSn, I2C0 SCL, UART0 RX |
| 23 | GND | — |
| 24 | GP18 | SPI0 SCK, I2C1 SDA |
| 25 | GP19 | SPI0 TX, I2C1 SCL |
| 26 | GP20 | — |
| 27 | GP21 | I2C0 SDA |
| 28 | GND | — |
| 29 | GP22 | — |
| 30 | RUN | (reset input) |
| 31 | GP26 | ADC0, I2C1 SDA |
| 32 | GP27 | ADC1, I2C1 SCL |
| 33 | AGND | — |
| 34 | GP28 | ADC2 |
| 35 | ADC_VREF | — |
| 36 | 3V3 (OUT) | — |
| 37 | 3V3_EN | — |
| 38 | GND | — |
| 39 | VSYS | — |
| 40 | VBUS | — |

Every GPIO listed above is 3.3 V logic (fixed, not tolerant of 5 V) and shares a PWM slice with a neighbor, so any of GP0–GP22 or GP26–GP28 can drive a PWM buzzer tone.

## What this project's Inky Pack already claims

See [`pico-inky-pack.md`](pico-inky-pack.md) — the display + buttons take GP12–14 and GP17–21 (18 and 20 collide with button C/DC — see that doc), leaving the rest of the table above genuinely free.
