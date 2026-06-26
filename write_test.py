#!/usr/bin/env python3
"""
Standalone NDEF write tester. Writes a URL onto whatever NTAG215 is on the
reader, independent of the API.

Usage:
    python3 write_test.py "https://yourdomain.com/tags/DEADBEEF"
    python3 write_test.py "https://yourdomain.com/tags/DEADBEEF" /dev/cu.usbmodem21201

Steps: place a tag on the reader, then run this. Requires pyserial.
"""

import sys
import glob
import time

try:
    import serial
except ImportError:
    sys.exit("pyserial not installed. Run:  pip install pyserial")

BAUD = 9600


def find_port():
    c = (glob.glob("/dev/cu.usbmodem*") + glob.glob("/dev/cu.usbserial*")
         + glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*"))
    if not c:
        sys.exit("No Arduino serial port found. Pass it as the 2nd argument.")
    return c[0]


def main():
    if len(sys.argv) < 2:
        sys.exit('Usage: python3 write_test.py "<url>" [port]')
    url = sys.argv[1]
    port = sys.argv[2] if len(sys.argv) > 2 else find_port()

    print(f"Connecting to {port} ...")
    with serial.Serial(port, BAUD, timeout=1) as ser:
        time.sleep(2)               # board resets on open
        ser.reset_input_buffer()
        print(f"Writing: {url}\nKeep the tag on the reader...")
        ser.write(f"WRITE:{url}\n".encode())

        deadline = time.time() + 5
        while time.time() < deadline:
            line = ser.readline().decode("utf-8", errors="replace").strip()
            if not line:
                continue
            print(" <", line)
            if line.startswith("WROTE:OK"):
                print("Success.")
                return
            if line.startswith("ERR:"):
                print("Failed.")
                return
        print("Timed out — was a tag on the reader?")


if __name__ == "__main__":
    main()
