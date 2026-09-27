"""
test/test_main.py -- SMOKE TEST: main.py imports cleanly and its pieces exist.

    mpremote connect <port> run test/test_main.py

Deliberately does NOT call main.main() -- that starts the real infinite
clock loop, which is the whole system, not a unit test of anything. This
just catches import/syntax errors (missing module, typo'd name) fast --
exactly the class of bug that took down the first hardware bring-up
(picographics not installed) before any of the more specific tests here
would even get a chance to run.
"""

print("=== test_main ===")
ok = True


def check(name, cond):
    global ok
    if cond:
        print("PASS:", name)
    else:
        ok = False
        print("FAIL:", name)


try:
    import main
    check("main.py imports without error", True)
except Exception as exc:
    check("main.py imports without error", False)
    print("  ", repr(exc))
    main = None

if main is not None:
    check("main.main is callable", callable(getattr(main, "main", None)))
    check("main.poll_button is callable", callable(getattr(main, "poll_button", None)))
    check("main.ButtonState exists", hasattr(main, "ButtonState"))

print("PASS: main.py smoke test passed" if ok else "test_main: FAILED, see above")
