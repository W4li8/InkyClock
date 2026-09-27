#!/usr/bin/env bash
# build/fetch_firmware.sh -- download Pimoroni's MicroPython UF2 for the
# Pico 2 W into build/ (gitignored -- see ../.gitignore).
#
# This project needs Pimoroni's firmware, not stock MicroPython: the display
# code (src/display.py) imports `picographics`/`pimoroni`, which are native
# modules only present in Pimoroni's build -- see docs/pico-inky-pack.md.
#
# Usage:
#   build/fetch_firmware.sh                 # fetch the pinned FW_VERSION below
#   build/fetch_firmware.sh v1.30.0         # fetch a specific version instead
#
# To actually flash it: put the Pico in bootloader mode (hold BOOTSEL while
# plugging in, or if it's already running any MicroPython build:
#   mpremote connect <port> bootloader
# then copy the .uf2 this script downloads onto the RP2350/RPI-RP2 drive that
# appears -- the board flashes itself and reboots automatically.

set -euo pipefail

FW_VERSION="${1:-v1.29.0}"   # pinned version this project was built/tested against
REPO="pimoroni/pimoroni-pico-rp2350"   # RP2350-based boards (Pico 2 / Pico 2 W); the
                                        # original "pimoroni-pico" repo is for RP2040 only
ASSET="rpi_pico2_w-${FW_VERSION}-micropython.uf2"
URL="https://github.com/${REPO}/releases/download/${FW_VERSION}/${ASSET}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="${SCRIPT_DIR}/${ASSET}"

echo "Fetching ${URL}"
curl -sL -o "${OUT}" "${URL}"

if ! file "${OUT}" | grep -q "UF2 firmware image"; then
    echo "Download doesn't look like a UF2 image -- check FW_VERSION/URL above." >&2
    rm -f "${OUT}"
    exit 1
fi

echo "Saved to ${OUT}"
