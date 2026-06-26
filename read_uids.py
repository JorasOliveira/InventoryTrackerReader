#!/usr/bin/env python3
"""
Read RFID UIDs from the Arduino RC522 reader and collect them into a list.

For now this just keeps the scans in memory (a Python list) and prints the
running list after each scan. Later we can swap the storage for a file,
database, etc.

Usage:
    python3 read_uids.py                        # auto-detect port
    python3 read_uids.py /dev/cu.usbmodem21201  # specify port

Requires pyserial:  pip install pyserial
"""

import sys
import glob
import time

try:
    import serial  # pyserial
except ImportError:
    sys.exit("pyserial not installed. Run:  pip install pyserial")

BAUD = 9600


def find_port():
    """Pick a likely Arduino serial port if one wasn't given."""
    candidates = (
        glob.glob("/dev/cu.usbmodem*") + glob.glob("/dev/cu.usbserial*")  # macOS
        + glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*")           # Linux
    )
    if not candidates:
        sys.exit("No Arduino serial port found. Pass it explicitly, e.g.\n"
                 "  python3 read_uids.py /dev/cu.usbmodem21201")
    return candidates[0]


def main():
    port = sys.argv[1] if len(sys.argv) > 1 else find_port()
    print(f"Connecting to {port} @ {BAUD} baud ...")

    # The list that holds every scanned UID, in order.
    tags = []

    # Opening the port resets the Arduino; give it a moment to boot.
    with serial.Serial(port, BAUD, timeout=1) as ser:
        time.sleep(2)
        print("Listening. Present a tag to the reader. Press Ctrl+C to stop.\n")

        while True:
            line = ser.readline().decode("utf-8", errors="replace").strip()
            if not line.startswith("UID:"):
                continue  # ignore "READY" and any noise

            uid = line[len("UID:"):].strip()
            tags.append(uid)

            print(f"Scanned: {uid}")
            print(f"  total scans: {len(tags)}")
            print(f"  all tags so far: {tags}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
