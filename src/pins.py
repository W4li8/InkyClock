"""
pins.py -- Central pin map for the InkyClock project
(Raspberry Pi Pico 2 W + Pimoroni Pico Inky Pack)

Import this instead of hardcoding GPIO numbers elsewhere, so every pin
conflict gets caught in one place instead of discovered on the bench.

    from pins import BUZZER, BUTTON_A

Sources: docs/pico-2-w-pinout.md, docs/pico-inky-pack.md, docs/buzzer-notes.md
"""

# ---------------------------------------------------------------------------
# Pico Inky Pack display (UC8151 e-paper).
# Driven internally by picographics.PicoGraphics(DISPLAY_INKY_PACK) -- you
# never wire these up or reference them directly. Listed here only so this
# file is a complete map for collision-checking new additions.
# ---------------------------------------------------------------------------
DISPLAY_CS    = 17  # SPI chip-select
DISPLAY_CLK   = 18  # SPI clock (SCK)
DISPLAY_MOSI  = 19  # SPI data out
DISPLAY_DC    = 20  # Data/Command select line (see docs/pico-inky-pack.md)
DISPLAY_RESET = 21  # Hardware reset
DISPLAY_BUSY  = 26  # Busy flag, display -> Pico, high while refreshing

# ---------------------------------------------------------------------------
# Pico Inky Pack buttons (pimoroni.Button / machine.Pin, pull-up, active-low)
# ---------------------------------------------------------------------------
BUTTON_A = 12
BUTTON_B = 13
BUTTON_C = 14

# Defined in Pimoroni's shared board template but NOT confirmed to have an
# actual switch on the retail Pico Inky Pack (only 3 buttons are documented/
# sold). Treated as reserved until checked with a continuity test -- don't
# hand these to something else without verifying first.
BUTTON_D_UP_UNCONFIRMED   = 15
BUTTON_E_DOWN_UNCONFIRMED = 11

# ---------------------------------------------------------------------------
# Claimed internally by the Pico 2 W's on-board CYW43439 wireless chip.
# Not present on the 40-pin header at all on a *_W board -- unusable, listed
# here only as a reminder not to reach for them.
# ---------------------------------------------------------------------------
WIRELESS_POWER_ON    = 23  # unusable on Pico 2 W
WIRELESS_SPI_DATA_IRQ = 24  # unusable on Pico 2 W
WIRELESS_SPI_CS       = 25  # unusable on Pico 2 W (this is GP25/onboard LED on a non-W Pico)
WIRELESS_SPI_CLK_ADC  = 29  # unusable on Pico 2 W (this is VSYS/3 ADC on a non-W Pico)

# ---------------------------------------------------------------------------
# Alarm buzzer (added by this project)
# ---------------------------------------------------------------------------
BUZZER = 22
# Simple single-pin hookup: GP22 --[passive piezo]-- GND (physical pin 28).

# Optional louder bridge-tied (BTL) drive: same-slice PWM channel pair driven
# in antiphase across the piezo for ~2x voltage swing (+6 dB). Use this PAIR
# instead of BUZZER above, not in addition to it, for the same physical piezo.
BUZZER_BRIDGE_A = 2  # PWM slice 1, channel A -- normal phase
BUZZER_BRIDGE_B = 3  # PWM slice 1, channel B -- invert=True in software
# GP2/GP3 are physically adjacent (header pins 4 & 5) with a GND right next
# to them at pin 3, and don't collide with the default UART0 console on
# GP0/GP1. See docs/buzzer-notes.md for the wiring/code.

# ---------------------------------------------------------------------------
# Genuinely free for anything else (RTC via I2C, light/battery sensor, etc.)
# ---------------------------------------------------------------------------
FREE_PINS = (0, 1, 4, 5, 6, 7, 8, 9, 16, 27, 28)
# GP0/GP1 default to UART0 TX/RX (USB-serial REPL) -- fine to reuse, but you
# lose the hardware UART console if you do.
# GP27/GP28 double as ADC1/ADC2 if you want an analog sensor later.
# (GP2/GP3 are free too if you skip the bridge-tied buzzer wiring above.)
