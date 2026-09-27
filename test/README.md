# InkyClock Tests

One test file per `src/*.py` module, each runnable independently against a connected board — no test framework, no fixtures, just a script you point `mpremote` at.

```
mpremote connect <port> run test/test_<name>.py
```

`mpremote run` uploads and executes the file directly without permanently copying it to the board, so these never need to be deployed alongside the real app code. They import the on-device `src/*.py` modules by name (`import buzzer`, `import wifi`, ...), so those need to already be on the board — normal after `build/flash.sh`.

| Test | Checks | How it's verified |
|---|---|---|
| `test_pins.py` | No two constants in `pins.py` claim the same GPIO; nothing overlaps the wireless-reserved pins | Automatic (PASS/FAIL) |
| `test_config.py` | `config.py` constants are in sane ranges/relationships | Automatic |
| `test_secrets.py` | `secrets.py` exists and isn't still the placeholder | Automatic |
| `test_alarm.py` | Digit editing, wraparound, enable/disable, ring-check gating | Automatic |
| `test_main.py` | `main.py` imports cleanly, its pieces exist (does **not** run the real clock loop) | Automatic |
| `test_persist.py` | Flash-backed state file: missing/round-trip/corrupt-file handling | Automatic |
| `test_wifi.py` | Wi-Fi joins, time-sync API call succeeds, radio powers back down, checkpoint/restore round-trip | Automatic |
| `test_buzzer.py` | Piezo buzzer on `pins.BUZZER` | **Human**: listen for it |
| `test_display.py` | E-ink display draws each view correctly | **Human**: look at the screen |

The first six need no hardware beyond the Pico itself running MicroPython — they're regression tests for logic bugs (the kind of off-by-one or typo that's easy to introduce and easy to miss just reading a diff). `test_wifi.py` needs Wi-Fi in range and a valid `secrets.py`. `test_buzzer.py` and `test_display.py` need the actual peripherals wired/attached and a person watching/listening — there's no way to check sound or pixels from software, so those two print step-by-step instructions instead of PASS/FAIL.

Run all the automatic ones in one go:

```bash
for t in pins config secrets alarm main persist wifi; do
    echo "--- $t ---"
    mpremote connect <port> run test/test_$t.py
done
```
