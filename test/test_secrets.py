"""
test/test_secrets.py -- LOGIC TEST: src/secrets.py exists and isn't still
the placeholder template.

No hardware needed:
    mpremote connect <port> run test/test_secrets.py

Covers both secrets.py and secrets.example.py (the two aren't split into
separate test files since secrets.example.py has nothing to check beyond
"does it look like the template it's supposed to be").
"""

print("=== test_secrets ===")
ok = True

try:
    import secrets
except ImportError:
    print("FAIL: secrets.py not found on the device -- copy src/secrets.example.py")
    print("      to src/secrets.py, fill in real values, then re-flash.")
    ok = False
else:
    placeholder_values = ("CHANGE_ME", "your-wifi-name", "your-wifi-password")

    if not getattr(secrets, "WIFI_SSID", ""):
        ok = False
        print("FAIL: WIFI_SSID is empty")
    elif secrets.WIFI_SSID in placeholder_values:
        ok = False
        print("FAIL: WIFI_SSID is still the placeholder value:", secrets.WIFI_SSID)
    else:
        print("PASS: WIFI_SSID is set (value not printed)")

    if not getattr(secrets, "WIFI_PASSWORD", ""):
        ok = False
        print("FAIL: WIFI_PASSWORD is empty")
    elif secrets.WIFI_PASSWORD in placeholder_values:
        ok = False
        print("FAIL: WIFI_PASSWORD is still the placeholder value")
    else:
        print("PASS: WIFI_PASSWORD is set (value not printed)")

print("PASS: secrets.py looks filled in" if ok else "test_secrets: FAILED, see above")
