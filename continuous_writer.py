#!/usr/bin/env python3
"""
Continuously listen for NTAG215 tags on the RC522 reader.

Keeps a list of UIDs we've already handled this session:
  - NEW uid      -> write the URL onto the tag, remember it
  - SEEN uid     -> do nothing

Usage:
    python3 continuous_writer.py                 # auto-detect port
    python3 continuous_writer.py /dev/cu.usbmodem21201

Requires pyserial.  Press Ctrl+C to stop.
"""

import sys
import glob
import time

try:
    import serial
except ImportError:
    sys.exit("pyserial not installed. Run:  pip install pyserial")

BAUD = 9600

# URL written onto each new tag. Put "{uid}" anywhere to embed the tag's UID,
# e.g. "https://yourdomain.com/tags/{uid}". As written, every new tag gets the
# same URL.
URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=RDdQw4w9WgXcQ"


def find_port():
    c = (glob.glob("/dev/cu.usbmodem*") + glob.glob("/dev/cu.usbserial*")
         + glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*"))
    if not c:
        sys.exit("No Arduino serial port found. Pass it as an argument.")
    return c[0]


def normalize_uid(raw):
    """'04 AB CD EF' -> '04ABCDEF'."""
    return raw.replace(" ", "").upper()


def write_url(ser, url):
    """Send WRITE:<url> and wait for the firmware's result. Returns True on OK."""
    ser.reset_input_buffer()
    ser.write(f"WRITE:{url}\n".encode())
    deadline = time.time() + 5
    while time.time() < deadline:
        line = ser.readline().decode("utf-8", errors="replace").strip()
        if line.startswith("WROTE:OK"):
            return True
        if line.startswith("ERR:"):
            print(f"    write failed: {line}")
            return False
    print("    write timed out (tag still on the reader?)")
    return False


def main():
    port = sys.argv[1] if len(sys.argv) > 1 else find_port()
    print(f"Connecting to {port} @ {BAUD} baud ...")

    seen = []  # UIDs handled this session

    with serial.Serial(port, BAUD, timeout=1) as ser:
        time.sleep(2)  # board resets when the port opens
        print("Listening for tags. Present a tag. Press Ctrl+C to stop.\n")

        while True:
            line = ser.readline().decode("utf-8", errors="replace").strip()
            if not line.startswith("UID:"):
                continue

            uid = normalize_uid(line[len("UID:"):])

            if uid in seen:
                print(f"{uid}  -> already seen, skipping")
                continue

            seen.append(uid)
            url = URL.replace("{uid}", uid)
            print(f"{uid}  -> NEW, writing: {url}")
            if write_url(ser, url):
                print(f"    OK  ({len(seen)} tag(s) handled this session)")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
