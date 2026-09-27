"""
test/test_wifi.py -- HARDWARE TEST: Wi-Fi radio + time-sync API.

Run against the connected board:
    mpremote connect <port> run test/test_wifi.py

Needs a real src/secrets.py already on the device (this test imports it
indirectly via wifi.py) -- copy it there first if you haven't:
    mpremote connect <port> fs cp src/secrets.py :

Unlike the buzzer/display tests, this one is self-checking: PASS/FAIL lines
below reflect real success/failure, no eyes/ears needed.
"""
import wifi

print("=== test_wifi ===")

print("Connecting...")
wlan = wifi.connect()
if wlan is None:
    print("FAIL: could not join Wi-Fi -- check src/secrets.py credentials")
else:
    print("PASS: connected, ip =", wlan.ifconfig()[0])

    ts = wifi.TimeSync()
    print("Fetching from", __import__("config").TIME_API_URL)
    result = ts._fetch_local_datetime()
    if result is None:
        print("FAIL: time API call failed -- check config.TIME_API_URL / docs/time-sync.md")
    else:
        y, mo, d, wd, hh, mm, ss = result
        print(f"PASS: got {y:04}-{mo:02}-{d:02} {hh:02}:{mm:02}:{ss:02} (weekday={wd})")

    wifi.disconnect()
    print("Radio powered back down (wifi.radio_active() should now be False).")
    print("radio_active() ->", wifi.radio_active())
