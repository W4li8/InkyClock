"""
test/test_persist.py -- LOGIC TEST: persist.py's flash-backed state file.

Run against the connected board:
    mpremote connect <port> run test/test_persist.py

No hardware beyond the flash filesystem (always present). Backs up any
real state.json first and restores it afterward, so this doesn't clobber
whatever the real app has actually persisted.
"""
import uos

import persist

print("=== test_persist ===")
ok = True


def check(name, cond, detail=""):
    global ok
    if cond:
        print("PASS:", name)
    else:
        ok = False
        print("FAIL:", name, detail)


had_real_state = False
try:
    uos.stat(persist.STATE_FILE)
    had_real_state = True
    uos.rename(persist.STATE_FILE, persist.STATE_FILE + ".testbak")
except OSError:
    pass

try:
    try:
        uos.remove(persist.STATE_FILE)
    except OSError:
        pass
    check("load() with no file returns {}", persist.load() == {})

    sample = {"datetime": [2026, 9, 27, 6, 12, 34, 56]}
    persist.save(sample)
    check("save()/load() round-trips", persist.load() == sample)

    with open(persist.STATE_FILE, "w") as f:
        f.write("{not valid json")
    check("load() with a corrupt file returns {} (doesn't raise)", persist.load() == {})

finally:
    try:
        uos.remove(persist.STATE_FILE)
    except OSError:
        pass
    if had_real_state:
        uos.rename(persist.STATE_FILE + ".testbak", persist.STATE_FILE)
        print("(restored the real state.json that was here before this test)")

print("PASS: all persist.py checks passed" if ok else "test_persist: FAILED, see above")
