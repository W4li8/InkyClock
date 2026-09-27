"""
test/test_config.py -- LOGIC TEST: config.py constants are in sane ranges.

No hardware needed:
    mpremote connect <port> run test/test_config.py

Catches the "typo'd a constant and it silently does something weird" class
of bug (e.g. ALARM_LONG_PRESS_S = 3 vs "3", or a negative interval) before
it shows up as confusing runtime behaviour.
"""
import config

print("=== test_config ===")
ok = True


def check(name, cond, detail=""):
    global ok
    if cond:
        print("PASS:", name)
    else:
        ok = False
        print("FAIL:", name, detail)


check("TIME_API_URL is a non-empty http(s) URL",
      isinstance(config.TIME_API_URL, str) and config.TIME_API_URL.startswith(("http://", "https://")))
check("SYNC_INTERVAL_S > 0", config.SYNC_INTERVAL_S > 0)
check("0 <= SYNC_T0_HOUR <= 23", 0 <= config.SYNC_T0_HOUR <= 23)
check("0 <= SYNC_T0_MINUTE <= 59", 0 <= config.SYNC_T0_MINUTE <= 59)
check("SYNC_RETRY_COUNT >= 1", config.SYNC_RETRY_COUNT >= 1)
check("SYNC_RETRY_INTERVAL_S > 0", config.SYNC_RETRY_INTERVAL_S > 0)
check("WIFI_CONNECT_TIMEOUT_S > 0", config.WIFI_CONNECT_TIMEOUT_S > 0)

check("0 <= DEFAULT_ALARM_HOUR <= 23", 0 <= config.DEFAULT_ALARM_HOUR <= 23)
check("0 <= DEFAULT_ALARM_MINUTE <= 59", 0 <= config.DEFAULT_ALARM_MINUTE <= 59)
check("ALARM_LONG_PRESS_S > 0", config.ALARM_LONG_PRESS_S > 0)
check("ALARM_BLINK_PERIOD_S > 0", config.ALARM_BLINK_PERIOD_S > 0)
check("ALARM_RING_FLASH_HZ > 0", config.ALARM_RING_FLASH_HZ > 0)

check("MAIN_LOOP_TICK_S > 0", config.MAIN_LOOP_TICK_S > 0)
check("IDLE_LIGHTSLEEP_S > 0", config.IDLE_LIGHTSLEEP_S > 0)
check("IDLE_LIGHTSLEEP_S >= MAIN_LOOP_TICK_S (idle should be the *longer* tick)",
      config.IDLE_LIGHTSLEEP_S >= config.MAIN_LOOP_TICK_S)

check("HEARTBEAT_WIFI_HZ > 0", config.HEARTBEAT_WIFI_HZ > 0)
check("HEARTBEAT_IDLE_HZ > 0", config.HEARTBEAT_IDLE_HZ > 0)
check("HEARTBEAT_WIFI_HZ > HEARTBEAT_IDLE_HZ (fast while connected, slow while idle)",
      config.HEARTBEAT_WIFI_HZ > config.HEARTBEAT_IDLE_HZ)

print("PASS: all config values sane" if ok else "test_config: FAILED, see above")
