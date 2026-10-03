#!/usr/bin/env python3
"""
tools/serial_logger.py -- passively log everything the board prints, across
however many hours you need, without ever interrupting it.

Why this exists: mpremote exec/run/fs always sends a break to get REPL
control, which kills main.py's loop if it's running (see CLAUDE.md) --
including a single read-only status check. That made "did the clock survive
overnight" impossible to actually verify without disturbing the very thing
being checked. This script opens the serial port the same passive way (no
break, confirmed live) and just appends every line to a log file with a
timestamp, so a crash/reboot/anything unexpected leaves a real trace instead
of needing to be reconstructed after the fact.

Disconnection handling, rewritten after a real failure: the first version
logged one "retrying in 2s" line per retry attempt, forever, with no state
tracking. Across a real multi-day gap (the Pico was unreachable from
2026-09-27 to 2026-10-02) that produced 24,669 near-identical lines -- 99%
of the entire log -- with no way to tell "how long was it actually gone"
without manually diffing timestamps across thousands of lines. Retrying
every 2s internally is still fine (quick to notice when the board comes
back); what changed is LOGGING only on state transitions (first
disconnect, periodic "still down" summaries, reconnect) instead of every
single attempt.

Usage:
    python3 tools/serial_logger.py [port] [logfile]
    python3 tools/serial_logger.py                                    # defaults below
    python3 tools/serial_logger.py /dev/tty.usbmodem1101 run.log

Run it in the background (nohup ... &) so it survives across terminal
sessions. It holds the serial port open continuously, so any mpremote
command needs it killed first (it'll auto-reconnect once you're done --
see the retry loop below) -- this project's own debugging sessions do
exactly that: kill it, run mpremote, restart it.
"""
import sys
import time
import datetime

import serial

DEFAULT_PORT = "/dev/tty.usbmodem1101"
DEFAULT_LOG = "overnight.log"
RETRY_INTERVAL_S = 2       # how often to actually try reopening the port
SUMMARY_INTERVAL_S = 300   # how often to log a "still down" line while disconnected (5 min)


def now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def format_duration(seconds):
    """'5 days, 7:52:14' / '2:15:30' style, not raw seconds -- the whole
    point is to be readable at a glance without doing timestamp math."""
    td = datetime.timedelta(seconds=int(seconds))
    return str(td)


def main():
    port = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PORT
    log_path = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_LOG

    with open(log_path, "a", buffering=1) as f:
        f.write(f"\n=== logger (re)started at {now()}, port={port} ===\n")

        disconnected_since = None   # time.time() of the first error in the current streak, or None
        last_summary_at = None      # time.time() of the last "still down" line we wrote

        while True:
            try:
                ser = serial.Serial(port, 115200, timeout=1, dsrdtr=False, rtscts=False)
                if disconnected_since is not None:
                    down_for = format_duration(time.time() - disconnected_since)
                    f.write(f"[{now()}] RECONNECTED after {down_for} unreachable\n")
                    disconnected_since = None
                    last_summary_at = None
                f.write(f"[{now()}] serial port opened\n")
                buf = b""
                while True:
                    chunk = ser.read(256)
                    if chunk:
                        buf += chunk
                        while b"\n" in buf:
                            line, buf = buf.split(b"\n", 1)
                            f.write(f"[{now()}] {line.decode(errors='replace')}\n")
            except Exception as e:
                t = time.time()
                if disconnected_since is None:
                    disconnected_since = t
                    last_summary_at = t
                    f.write(f"[{now()}] DISCONNECTED: {e!r} -- retrying every {RETRY_INTERVAL_S}s, "
                            f"will log a summary every {SUMMARY_INTERVAL_S}s while still down\n")
                elif t - last_summary_at >= SUMMARY_INTERVAL_S:
                    last_summary_at = t
                    down_for = format_duration(t - disconnected_since)
                    f.write(f"[{now()}] still down, unreachable for {down_for} so far\n")
                time.sleep(RETRY_INTERVAL_S)


if __name__ == "__main__":
    main()
