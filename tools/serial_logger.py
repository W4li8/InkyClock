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


def now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def main():
    port = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PORT
    log_path = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_LOG

    with open(log_path, "a", buffering=1) as f:
        f.write(f"\n=== logger (re)started at {now()}, port={port} ===\n")
        while True:
            try:
                ser = serial.Serial(port, 115200, timeout=1, dsrdtr=False, rtscts=False)
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
                f.write(f"[{now()}] SERIAL ERROR: {e!r} -- retrying in 2s\n")
                time.sleep(2)


if __name__ == "__main__":
    main()
