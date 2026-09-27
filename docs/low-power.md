# Low Power Design

Three things happened here, from a conversation about whether the alarm could sleep deeply between events: one worked as asked, one didn't work and was documented as a limitation, and the third — trying anyway with a bounded-duration compromise — turned out to be an active **correctness bug**, not just a missed optimization. Read the whole thing before touching `main.py`'s sleep call again.

## 1. Wi-Fi radio off between syncs (this works, and is the bigger win)

`wifi.py`'s `TimeSync` calls `disconnect()` (`wlan.active(False)`) as soon as a sync slot's attempts conclude (`_conclude()`), and only reconnects for the next scheduled attempt. The CYW43439 draws real current (tens of mA) whenever associated; keeping it off except for a brief burst every ~4 hours is a straightforward, large saving with no downside. `radio_active()` exposes the current state; `main.py` uses it to drive the heartbeat LED's Wi-Fi-status coupling.

## 2. Button presses do NOT wake `machine.lightsleep()` early on rp2

The original idea: sleep for up to a minute at a stretch (or longer), waking either on a timer or instantly via a `Pin.irq()` on a button press. The timer half is fine; the button half doesn't work on this port, confirmed from the MicroPython source. **[`ports/rp2/modmachine.c`](https://github.com/micropython/micropython/blob/master/ports/rp2/modmachine.c)**, the timed `lightsleep(ms)` path, on RP2350 (the branch that actually applies to this board — the RP2040 branch uses a different, RTC-inclusive bit set, see §3 below for why that distinction turned out to matter a lot):

```c
#elif PICO_RP2350
clocks_hw->sleep_en0 = CLOCKS_SLEEP_EN0_CLK_REF_POWMAN_BITS | CLOCKS_SLEEP_EN0_CLK_SYS_POWMAN_BITS;
uint32_t sleep_en1 = CLOCKS_SLEEP_EN1_CLK_REF_TICKS_BITS | CLOCKS_SLEEP_EN1_CLK_SYS_TIMER0_BITS;
...
__wfi();
```

Before the single `__wfi()` call, the code narrows which peripheral clocks stay powered. GPIO's own clock domain (`IO_BANK0`) isn't in that list on either chip variant — so a button-press edge can't even be latched, let alone raise an interrupt, while the CPU is asleep. Only the timer alarm it set up for the requested delay (or USB activity) can end the `__wfi()`. `Pin.irq()` also has no `wake=` parameter on rp2 at all (unlike, say, the esp32 port), confirming there's no supported way to register a GPIO as a sleep wake source through the normal API. (There's a lower-level escape hatch — the SDK's `gpio_set_dormant_irq_enabled()`, used internally only to wire up the CYW43 host-wake pin for the argument-less fully-dormant `lightsleep()` call — but it isn't exposed to Python and wasn't attempted here.)

**Conclusion at the time:** since a press can't interrupt a timed sleep, bound the sleep length instead of waiting for an interrupt. That reasoning was sound. What it was applied to next was the actual bug:

## 3. `machine.lightsleep()` freezes `machine.RTC()` for its entire duration — confirmed, and this is why the clock kept "stopping"

This was found the hard way, after this session's clock repeatedly appeared to stop advancing during real (non-testing) overnight/multi-hour runs, with no crash, no traceback, nothing in the logs — just silence, followed by a frozen RTC reading from whenever the loop had last drawn the clock. Every earlier theory (interrupted boot syncs, a display-driver crash from rapid button presses) turned out to be real bugs in their own right, fixed along the way, but **none of them were the actual root cause of the recurring symptom** — this was.

Isolated, reproducible confirmation (no WiFi, no display, no other subsystem involved):

```python
import time, machine
rtc = machine.RTC()
for i in range(200):
    machine.lightsleep(250)
    print(rtc.datetime())   # prints the EXACT SAME timestamp all 200 times
```

200 iterations of `lightsleep(250)` — 50 real seconds — and the RTC never advanced once. For comparison, `time.ticks_ms()` across the same kind of loop tracked real elapsed time correctly (2503ms measured for 10×250ms, effectively exact). So the CPU's own free-running tick counter survives `lightsleep()` fine; `machine.RTC()` does not.

Why the bug hid so well in short tests: a quick "reset, wait 15–30s, check" test mostly measures the *boot sync's* accuracy (which sets the RTC fresh right before the loop starts, and 15-30s of even-partially-correct ticking looks close enough to right). It's only once `MODE_CLOCK`'s idle path has been running for a while — spending the overwhelming majority of its time *inside* the very sleep call that freezes the clock — that the RTC visibly diverges from real time by however long the device has actually been idling. The longer it runs undisturbed, the worse it looks, which is exactly backwards from what you'd want out of a "let it run overnight" test and exactly why it took this long to pin down.

The exact internal reason `machine.RTC()` doesn't survive `lightsleep()` on this RP2350 build — despite the POWMAN clock bits nominally staying enabled per the source above — wasn't traced further than this; the fix doesn't require knowing why, just knowing not to rely on it.

## What's actually implemented (current, correct)

`main.py`'s main-loop tick is a plain `time.sleep_ms()`, always — never `machine.lightsleep()`, in any mode:

- `config.MAIN_LOOP_TICK_S` (20ms) — `MODE_EDIT`, `MODE_RINGING`, a button currently held, or the Wi-Fi radio active. Needed for accurate long-press/flash timing.
- `config.IDLE_TICK_S` (250ms) — `MODE_CLOCK`, nothing held. Bounded short purely so a button press is still picked up promptly (no lightsleep-wake mechanism is involved anymore, so this is no longer working around anything — it's just "don't poll needlessly often").

This gives up the CPU-halt power saving `lightsleep()` would have provided during idle ticking — a real, known trade-off, not an oversight — in exchange for the clock actually working. The Wi-Fi-off saving from §1 is untouched and remains the meaningful power win; `time.sleep_ms()`'s own power draw during the wait is not something this project has measured or optimized further.

If deeper CPU-idle power savings are wanted later, the honest options are: (a) find and understand the actual RP2350/`machine.RTC()` interaction well enough to work around it (e.g., snapshot `rtc.datetime()` + a `ticks_ms()` reference at each successful sync, and compute "current time" from the `ticks_ms()` delta instead of reading `machine.RTC()` directly during normal operation, since `ticks_ms()` is confirmed lightsleep-safe) — real engineering effort, not attempted here; or (b) accept `time.sleep_ms()` as the ceiling for this project's power optimization and move on. Noted in `idea.txt`.
