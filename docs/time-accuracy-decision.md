# Decision: no battery-backed RTC, no UPS

Both were parked in `idea.txt` early on and are now explicitly dropped, not
just left unscheduled. Reasoning, with actual numbers, so this doesn't get
re-litigated later without cause.

## The actual reliability target

Stated goal (see `todo.txt`, 2026-09-27): don't miss the alarm by more than
**~10 minutes** when running on normal home mains power. That's the bar
everything below is measured against — not "never drift at all."

## Crystal drift between syncs is negligible against that bar

`wifi.TimeSync` resyncs against a time API every 4 hours and otherwise lets
the RP2350 count time on its own crystal in between. A typical low-cost
crystal of this class runs ±20 ppm; even a pessimistic ±100 ppm cheap part:

| Scenario | Elapsed time | Drift @ ±20 ppm | Drift @ ±100 ppm (pessimistic) |
|---|---|---|---|
| One sync interval | 4 h (14,400 s) | 0.29 s | 1.44 s |
| A full day of only *failed* syncs (6 windows missed in a row) | 24 h | 1.73 s | 8.64 s |
| A full week of only failed syncs | 7 days | 12.1 s | 60.5 s |

Even the worst-case row — a full week where every single 4-hourly sync
fails, which has never happened in this project's testing — is still an
order of magnitude under the 10-minute budget. Crystal drift was never the
risk this clock needed hardware to solve.

## The real risk is a power outage, and it's already handled

The only way this clock actually loses track of time is a power loss (no
battery-backed RTC means a cold boot resets `machine.RTC()` to epoch). Two
things already bound the damage from that, built this session:

1. **Boot-time resync-before-anything-else** — `main.py` syncs before it
   ever shows a clock face, so if mains power comes back and Wi-Fi/the
   internet are already up, the outage is invisible — correct time within
   the first sync attempt (seconds).
2. **`src/persist.py` flash checkpoint** (`PERSIST_CHECKPOINT_S` = 10 min)
   — covers exactly the gap case 1 doesn't: power recovers but the
   router/ISP modem is still rebooting (routers are often slower than a
   Pico to come back). `restore_from_flash()` gives a baseline accurate to
   within one checkpoint interval — 10 minutes, by construction — until
   Wi-Fi catches up and corrects it for real. This was built specifically
   to hit the 10-minute target above, not as a stopgap for something else.

What a battery-backed RTC (DS3231/PCF8523) or a UPS would each actually add
on top of that:

- **Battery-backed RTC**: survives the power loss itself and gives an
  exact timestamp at boot instead of a checkpoint-bounded estimate. But the
  checkpoint *already* meets the stated 10-minute bar — an RTC would only
  improve on a target that's already met, at the cost of an extra
  component, I2C wiring, and a coin cell to replace every 5–10 years.
- **UPS** (battery + boost circuit keeping the Pico powered through the
  outage): the only one of the two that actually helps *through* a
  multi-minute-plus outage rather than recovering after it. But: if mains
  power is out long enough for this to matter, the home router/modem is
  almost certainly also down (those aren't on this UPS), so Wi-Fi sync is
  unavailable regardless of whether the Pico itself stayed powered — a UPS
  buys "the display and buzzer still work," not "the clock stays
  internet-accurate." And a whole-house outage long enough to need this is
  rare enough on normal city power that it's outside what this project is
  trying to engineer around (see the SAIDI-style point below).
- Both ideas are specifically aimed at outages well beyond what "a modern
  city home's mains power" realistically produces — US grid reliability
  benchmarks (SAIDI, System Average Interruption Duration Index) put
  typical non-storm-year total outage time at low-single-digit hours
  *per year*, almost all of it as a handful of brief (seconds-to-minutes)
  blips that case 1/2 above already absorb without issue.

## Conclusion

The 4-hour sync + crystal-counted interim + 10-minute flash checkpoint
already meets the stated reliability target with wide margin, using
hardware already on the board. A battery-backed RTC and a UPS each solve a
real problem, but not one this clock actually has at realistic home-power
reliability levels — adding either would be solving for a failure mode
(multi-hour-plus whole-house outages) that's already rare, and whose
consequence (a stale clock until power *and* Wi-Fi both come back) is
already bounded to 10 minutes by design. Dropped, not revisited unless the
actual operating environment changes (e.g. deploying this somewhere with
materially worse grid reliability than a modern city home).
