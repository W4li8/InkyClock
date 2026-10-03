# E-ink refresh energy, cycle life, and the presence-sensor question

Prompted by: "would a presence sensor (PIR or mmWave) be worth adding so the
display doesn't needlessly refresh when no one's around to read it, or
would the sensor itself burn more power than it saves?" Short answer up
front: **no, skip it** -- the display's own refresh energy is already so
small that no presence sensor meaningfully improves on it, and the
cheapest "good enough" sensor (a basic PIR) has the wrong detection
model for this use case anyway (see below). The numbers:

## What a refresh actually costs

Per the UC8151D panel's published specs: **~26.4 mW typical during a
refresh**, standby (not refreshing) **under 0.01 µA** -- effectively free.
Refresh duration: **~2s full**, **~0.3s partial**.

- Full refresh energy: 26.4 mW x 2s = 52.8 mJ (~0.015 mWh, ~15 µWh).
- A separate commonly-cited figure (26 mA x 2s on a similar 2.9" panel,
  ~14.4 µAh/refresh at panel voltage) works out closer to ~48 µWh/refresh.
  These don't agree exactly (different panel batches/measurement setups),
  so treat **"tens of µWh per full refresh"** as the honest, order-of-
  magnitude number rather than a precise spec.
- Partial refresh is proportionally cheaper (~0.3s vs ~2s) -- call it a
  few µWh.

This project's main refresh driver is `main.py`'s once-per-minute
`MODE_CLOCK` redraw: 1,440 full refreshes/day. At "tens of µWh" each,
that's roughly **20-70 mWh/day** total from the display, depending on
which of the two figures above you trust. Edit/preview screen updates add
a handful more per session, negligible next to that.

## Cycle life: nowhere close to a limiting factor

No UC8151D-specific cycle-life number is published, but the figure the
e-paper industry broadly cites (E Ink's own "Pearl" generation spec) is
**~10 million refresh cycles** before contrast visibly degrades (a gradual
fade, not a hard failure). At this project's actual rate of 1,440
refreshes/day:

```
10,000,000 refreshes / 1,440 per day = ~6,944 days = ~19 years
```

...of continuous once-a-minute refreshing before even approaching that
number. Not a real constraint for an alarm clock.

## Would a presence sensor help? The math says no

This device runs on continuous USB/mains power (see
[`time-accuracy-decision.md`](time-accuracy-decision.md) -- there's no
battery in this design to extend), so "would it save power" is really
"would it save a *meaningful* amount of power," since tens of mWh/day is
already immaterial on a wall adapter either way. But doing the comparison
properly anyway, because the sensor's own baseline draw matters more than
intuition suggests:

| Sensor | Typical continuous current | Daily energy @ 3.3V | vs. display's own ~20-70 mWh/day budget |
|---|---|---|---|
| AM312 (ultra-low-power PIR) | ~8 µA | ~0.63 mWh/day | ~1-3% of it -- genuinely cheap |
| HC-SR501 (common PIR module) | ~50-65 µA | ~4.4 mWh/day | ~6-22% of it -- still cheap |
| HLK-LD2410S (low-power mmWave) | ~0.1 mA (100 µA) | ~7.9 mWh/day | ~11-40% of it -- noticeable bite |
| Waveshare HMMD (S3KM1110-based, 24GHz FMCW) | ~50 mA avg | ~3,960 mWh/day (**~4 Wh/day**) | **~57-198x the ENTIRE display budget** |
| HLK-LD2410 (standard mmWave) | ~80 mA | ~6,300-9,600 mWh/day (**6-10 Wh/day**) | **~100-480x the ENTIRE display budget** |

The standard LD2410 is a non-starter outright -- at ~80 mA continuous (it's
an always-transmitting FMCW radar, no deep-sleep state), it alone would
burn more power than this whole clock's every other subsystem combined
many times over, including the Wi-Fi radio's periodic sync bursts
(`docs/low-power.md`). A PIR (especially an ultra-low-power one like the
AM312) or the LD2410**S** low-power variant both cost less than the
display's own existing budget, so gating refreshes with one of those could
in principle be a net power win on paper.

In practice, though: the display's total budget is **tens of milliwatt-
hours per day** -- immeasurably small next to a USB wall adapter's
capacity, and already 19 years from its rated cycle life regardless of how
often it refreshes. There's no real power problem here for a sensor to
solve. The only way this becomes worth doing is for a *non-power* reason:
reducing visible refresh "flicker"/distraction in a dark room when no
one's there to see it -- a cosmetic argument, not an energy one.

## If pursued anyway: PIR is the wrong sensor type for this specific ask

The stated goal was "don't update when no one's there to **read the
time**" -- which includes someone lying still in bed looking at the clock,
not moving. A PIR only detects *change* in IR flux (motion) -- a
motionless person reading or lying still will "disappear" to a PIR after
its timeout, which is exactly the wrong failure mode here (the display
would stop updating while someone's actively looking at it). mmWave radar
(the LD2410 family specifically) is built to solve this: it detects
micro-Doppler motion down to breathing, so it reports *static human
presence*, not just movement -- the right detection model for "is someone
in the room," not "did someone just move."

So: if this were pursued for the cosmetic/flicker reason above rather than
power, **LD2410S** (the low-power mmWave variant, ~100 µA) would be the
right part on power grounds alone -- not a PIR, and definitely not the
standard LD2410.

## A specific candidate considered: Waveshare's HMMD sensor (S3KM1110)

Waveshare sells a 24GHz FMCW module ("Human Micro-Motion Detection mmWave
Sensor") built on the S3KM1110 chip, UART+GPIO interface, **native 3.3V**
supply and logic -- a real practical plus over the LD2410 family (which
commonly wants a 5V supply despite 3.3V-tolerant logic): it wires straight
to the Pico's own 3V3 rail and GPIOs with no level-shifter. It explicitly
detects "moving, standing, and motionless human bodies" -- i.e. it has the
right detection model (micro-Doppler/breathing-based static presence,
not just motion) for the original "someone's reading in bed" scenario,
same as the LD2410 family.

Its average current, though, is **~50 mA** -- see the table above: ~4
Wh/day, **~57-198x the display's entire power budget**. So on pure power
grounds it's in the same boat as the standard LD2410, not the LD2410S: it
would not save power, by a wide margin. On this specific device, though
(continuous USB/mains power, no battery), that's not actually a problem in
absolute terms -- 50 mA extra is well within what a Pico's USB supply and
3.3V regulator can provide alongside everything else here, and ~4 Wh/day
costs essentially nothing on a wall outlet. It just means the honest
framing for using this part is "nice-to-have presence detection for its
own sake" (right chip, easy 3.3V integration, no level-shifting), never
"this saves power" -- it provably doesn't, it only happens not to matter
on a mains-powered design.

Sources: [UC8151d datasheet](https://cdn-learn.adafruit.com/assets/assets/000/137/964/original/UC8151d.pdf) (via Adafruit) · [Pico Inky Pack product page](https://shop.pimoroni.com/en-us/products/pico-inky-pack) · [E-paper partial refresh power figures](https://zbotic.in/e-paper-partial-refresh-faster-updates-for-dynamic-content/) · [E-paper durability/cycle-life overview](https://techflare.net/how-long-does-e-paper-last-the-ultimate-durability-guide/) · AM312/HC-SR501 PIR current specs (vendor datasheets/community measurements) · [HLK-LD2410 module manual](https://seengreat.com/upload/file/86/HLK+LD2410+Life+Presence+Sensor+Module+Manual+V1.03(220629).pdf) · LD2410S low-power variant spec (Hi-Link product page) · [Waveshare HMMD mmWave Sensor product page](https://www.waveshare.com/hmmd-mmwave-sensor.htm) · [Waveshare HMMD Wiki](https://www.waveshare.com/wiki/HMMD_mmWave_Sensor).
