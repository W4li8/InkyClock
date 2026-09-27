# Low Power Design

Two changes went into this, from a conversation about whether the alarm could sleep deeply between events. One panned out as asked; the other didn't, and it's worth recording why so nobody re-tries it later.

## 1. Wi-Fi radio off between syncs (this works, and is the bigger win)

`wifi.py`'s `TimeSync` calls `disconnect()` (`wlan.active(False)`) as soon as a sync slot's attempts conclude (`_conclude()`), and only reconnects for the next scheduled attempt. The CYW43439 draws real current (tens of mA) whenever associated; keeping it off except for a brief burst every ~4 hours is a straightforward, large saving with no real downside for this use case. `radio_active()` exposes the current state so `main.py` can pick the right sleep primitive (see below).

## 2. Button presses do NOT wake `machine.lightsleep()` early on rp2

The original idea: sleep for up to a minute at a stretch (or longer), waking either on a timer (for the periodic clock/alarm/sync check) or instantly via a `Pin.irq()` on a button press. The timer half is fine. The button half doesn't work on this port, confirmed from the actual MicroPython source rather than assumed:

**[`ports/rp2/modmachine.c`](https://github.com/micropython/micropython/blob/master/ports/rp2/modmachine.c), the timed `lightsleep(ms)` path:**

```c
clocks_hw->sleep_en0 = CLOCKS_SLEEP_EN0_CLK_RTC_RTC_BITS;
clocks_hw->sleep_en1 = CLOCKS_SLEEP_EN1_CLK_SYS_TIMER_BITS;
...
__wfi();
```

Before the single `__wfi()` call, the code explicitly narrows which peripheral clocks stay powered to just RTC + TIMER (and USB, if not disabled). GPIO's own clock domain (`IO_BANK0`) is not in that list — so a button-press edge can't even be latched, let alone raise an interrupt, while the CPU is in this state. Only the timer alarm it set up for the requested delay (or USB activity) can end the `__wfi()`. The file's own `DEBUG_LIGHTSLEEP` comments corroborate this — they only ever mention observing `TIMER_IRQ` or `USBCTRL_IRQ` as the wake cause, never a GPIO IRQ.

**[`ports/rp2/machine_pin.c`](https://github.com/micropython/micropython/blob/master/ports/rp2/machine_pin.c):** `Pin.irq()` has no `wake=` parameter at all (unlike, say, the esp32 port's `Pin.irq(..., wake=machine.SLEEP)`), confirming there's no supported way to register a GPIO as a sleep wake source through the normal API.

There is a lower-level escape hatch — the Pico SDK's `gpio_set_dormant_irq_enabled()`, used internally by MicroPython only to wire up the CYW43 host-wake pin for the argument-less (fully dormant) `lightsleep()` call — but it isn't exposed to Python, would need raw register access to use for an arbitrary pin, is RP2040/RP2350-register-layout-specific, and hasn't been attempted here: not appropriate to hand a hobby project a fragile, unverified raw-register hack for this.

## What's actually implemented instead

Since a press can't interrupt a timed sleep, responsiveness has to come from **bounding the sleep length**, not from an interrupt:

- `config.MAIN_LOOP_TICK_S` (20ms) -- used while `MODE_EDIT`, `MODE_RINGING`, a button is currently held, or the Wi-Fi radio is active. Unchanged from the original polling design; needed for accurate long-press/blink/flash timing.
- `config.IDLE_LIGHTSLEEP_S` (250ms) -- used only when `MODE_CLOCK`, no button held, and the radio is off (`main.py`, tail of `main()`). Plenty precise for a per-minute clock and an alarm check, and a 250ms worst-case press-to-reaction lag is imperceptible next to the e-ink panel's own refresh time.

Net effect: same correctness guarantees as the original 20ms-everywhere loop, ~12x fewer wakes during normal idle ticking, on top of the (larger) Wi-Fi-off saving above.
