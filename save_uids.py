#!/usr/bin/env python3
"""
Listen to the Arduino RC522 reader over serial and append every scanned
RFID UID to a text file on the Desktop.

Usage:
    python3 save_uids.py                       # auto-detect port
    python3 save_uids.py /dev/cu.usbmodem11301 # specify port

Output file:  ~/Desktop/rfid_tags.txt
Each line:    2026-06-25 14:03:21  DE AD BE EF

Requires pyserial:  python3 -m pip install pyserial
"""

import sys
import glob
import time
from datetime import datetime
from pathlib import Path

try:
    import serial  # pyserial
except ImportError:
    sys.exit("pyserial not installed. Run:  python3 -m pip install pyserial")

BAUD = 9600
OUTFILE = Path.home() / "Desktop" / "rfid_tags.txt"


def find_port():
    """Pick a likely Arduino serial port if one wasn't given."""
    candidates = (
        glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*")  # Linux
        + glob.glob("/dev/cu.usbmodem*") + glob.glob("/dev/cu.usbserial*")  # macOS
    )
    if not candidates:
        sys.exit("No Arduino serial port found. Pass it explicitly, e.g.\n"
                 "  python3 save_uids.py /dev/ttyACM0")
    return candidates[0]


def main():
    port = sys.argv[1] if len(sys.argv) > 1 else find_port()
    print(f"Connecting to {port} @ {BAUD} baud ...")

    # Opening the port resets the Arduino; give it a moment to boot.
    with serial.Serial(port, BAUD, timeout=1) as ser:
        time.sleep(2)
        print(f"Listening. Saving UIDs to {OUTFILE}")
        print("Present a tag to the reader. Press Ctrl+C to stop.\n")

        while True:
            line = ser.readline().decode("utf-8", errors="replace").strip()
            if not line.startswith("UID:"):
                continue

            uid = line[len("UID:"):].strip()
            stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            record = f"{stamp}  {uid}"

            with open(OUTFILE, "a") as f:
                f.write(record + "\n")
            print("saved:", record)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
