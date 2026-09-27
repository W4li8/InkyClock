#!/usr/bin/env bash
# build/flash.sh -- deploy src/*.py onto a Pico 2 W already running
# Pimoroni's MicroPython (see fetch_firmware.sh if it isn't yet), then reset
# so main.py starts running immediately.
#
# Usage:
#   build/flash.sh [serial-port]
#   build/flash.sh                       # auto-detects a single usbmodem port
#   build/flash.sh /dev/tty.usbmodem1101 # or name it explicitly (multiple
#                                         # boards connected, Linux /dev/ttyACM0, etc.)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$(cd "${SCRIPT_DIR}/../src" && pwd)"

if ! command -v mpremote >/dev/null 2>&1; then
    echo "mpremote not found -- install it with: pip install mpremote" >&2
    exit 1
fi

if [ ! -f "${SRC_DIR}/secrets.py" ]; then
    echo "src/secrets.py is missing -- copy src/secrets.example.py to src/secrets.py" >&2
    echo "and fill in your Wi-Fi credentials first (it's gitignored, never committed)." >&2
    exit 1
fi

PORT="${1:-}"
if [ -z "${PORT}" ]; then
    CANDIDATES=(/dev/tty.usbmodem* /dev/ttyACM*)
    FOUND=()
    for p in "${CANDIDATES[@]}"; do
        [ -e "${p}" ] && FOUND+=("${p}")
    done
    if [ "${#FOUND[@]}" -eq 0 ]; then
        echo "No usbmodem/ttyACM serial port found -- is the Pico plugged in?" >&2
        exit 1
    elif [ "${#FOUND[@]}" -gt 1 ]; then
        echo "Multiple serial ports found, pass one explicitly: ${FOUND[*]}" >&2
        exit 1
    fi
    PORT="${FOUND[0]}"
fi

echo "Using port: ${PORT}"
echo "Copying src/*.py (except secrets.example.py) to the board..."

cd "${SRC_DIR}"
# main.py last: if anything above fails, the board keeps its previous
# (presumably working) main.py instead of being left with a half-updated set.
mpremote connect "${PORT}" fs cp \
    pins.py config.py alarm.py buzzer.py display.py wifi.py secrets.py main.py \
    :

echo "Resetting board so main.py runs..."
mpremote connect "${PORT}" reset

echo "Done. Watch it boot with: mpremote connect ${PORT}"
