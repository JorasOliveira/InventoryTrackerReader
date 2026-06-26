#!/usr/bin/env python3
"""
Tag controller (Hackaton) — desk-side software for the RC522 reader.

For every NTAG215 scanned on the Arduino, this script:
  1. reads the UID over serial,
  2. asks the API whether a tag with that UID already exists,
  3. if it EXISTS    -> opens the edit page in the browser,
  4. if it DOESN'T   -> creates it via the API, then opens the edit page.

(Writing the NDEF URL onto the physical tag is done by the Arduino firmware —
 that part is still TODO; see write_url_to_tag().)

Config via environment variables (with sensible defaults):
  API_URL   base URL of Guilherme's backend   (default http://localhost:8000)
  SITE_URL  base URL of the frontend / NDEF    (default = API_URL)
  PORT      serial port                        (default: auto-detect)

API contract assumed (adjust to match the real backend):
  GET  {API_URL}/tags/{uid}   -> 200 + JSON if exists, 404 if not
  POST {API_URL}/tags         -> create; body {"id": uid, ...}

Requires:  pip install pyserial requests
"""

import os
import sys
import glob
import time
import webbrowser

try:
    import serial  # pyserial
except ImportError:
    sys.exit("pyserial not installed. Run:  pip install pyserial requests")

try:
    import requests
except ImportError:
    sys.exit("requests not installed. Run:  pip install pyserial requests")

BAUD = 9600
# Defaults point at this Mac's LAN IP so a phone on the same Wi-Fi can reach
# both the API and the frontend. Override with env vars if the IP changes
# (it's DHCP-assigned) or when deploying to a real domain.
API_URL = os.environ.get("API_URL", "http://192.168.15.70:8000").rstrip("/")
SITE_URL = os.environ.get("SITE_URL", "http://192.168.15.70:5173").rstrip("/")
DEBOUNCE_SECONDS = 3  # ignore the same tag re-scanned within this window


def find_port():
    """Pick a likely Arduino serial port if PORT isn't set; None if absent."""
    if os.environ.get("PORT"):
        return os.environ["PORT"] if os.path.exists(os.environ["PORT"]) else None
    candidates = (
        glob.glob("/dev/cu.usbmodem*") + glob.glob("/dev/cu.usbserial*")  # macOS
        + glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*")           # Linux
    )
    return candidates[0] if candidates else None


def wait_for_port():
    """Block until a serial port is available, then return it. Survives unplugs."""
    port = find_port()
    if port:
        return port
    print("Waiting for the Arduino serial port (plug it in / re-plug it)...")
    while port is None:
        time.sleep(1)
        port = find_port()
    return port


def normalize_uid(raw):
    """'DE AD BE EF' -> 'DEADBEEF' (canonical key for URLs and the DB)."""
    return raw.replace(" ", "").upper()


def tag_exists(uid):
    """Look the tag up by its physical NFC UID (Strategy A).

    Returns the tag's JSON if it exists, None on 404. The backend keys tags by
    an internal UUID, so we use the dedicated /tags/by-uid/{nfc_uid} endpoint
    added for the reader.
    """
    resp = requests.get(f"{API_URL}/tags/by-uid/{uid}", timeout=5)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def open_page(uid):
    """Open the frontend page for this tag in the default browser.

    The frontend page at {SITE_URL}/tags/{uid} handles both cases itself:
    if the tag exists it shows the edit form, otherwise it shows the create
    form (device type chassi/modulo/bateria, data, inherited location). The
    actual POST/PUT to the API is done by that page, not by this script.
    """
    url = f"{SITE_URL}/t/{uid}"
    print(f"  opening {url}")
    webbrowser.open(url)


def write_url_to_tag(ser, uid):
    """Tell the Arduino to write the NDEF URL onto the physical tag.

    Sends 'WRITE:<url>' and waits for the firmware's 'WROTE:OK' / 'ERR:...'
    reply. The tag must still be on the reader. Returns True on success.
    """
    url = f"{SITE_URL}/t/{uid}"
    print(f"  writing NDEF to tag: {url}")

    ser.reset_input_buffer()                       # drop any pending UID lines
    ser.write(f"WRITE:{url}\n".encode())

    deadline = time.time() + 5
    while time.time() < deadline:
        line = ser.readline().decode("utf-8", errors="replace").strip()
        if line.startswith("WROTE:OK"):
            print("  NDEF write OK")
            return True
        if line.startswith("ERR:"):
            print(f"  NDEF write failed: {line}")
            return False
    print("  NDEF write timed out (is the tag still on the reader?)")
    return False


def handle_scan(ser, uid):
    """Run the full check/create flow for one scanned UID."""
    print(f"Scanned: {uid}")
    try:
        existing = tag_exists(uid)
    except requests.RequestException as e:
        print(f"  ! API unreachable ({e}); skipping.")
        return

    if existing:
        print("  tag exists -> open edit page")
        open_page(uid)
    else:
        print("  new tag -> write NDEF, open create page")
        write_url_to_tag(ser, uid)   # stamp the URL onto the physical tag
        open_page(uid)               # frontend shows the create form
    print()


def main():
    print(f"API:  {API_URL}\nSite: {SITE_URL}\n")

    last_uid, last_time = None, 0.0

    # Outer loop: (re)connect to the board. Flaky USB-serial adapters (e.g. CH340
    # clones) drop their /dev node on a glitch; instead of dying we wait for it
    # to come back and reconnect automatically.
    while True:
        port = wait_for_port()
        print(f"Connecting to {port} @ {BAUD} baud ...")
        try:
            with serial.Serial(port, BAUD, timeout=1) as ser:
                time.sleep(2)  # opening the port resets the Arduino; let it boot
                print("Ready. Present a tag. Press Ctrl+C to stop.\n")

                while True:
                    try:
                        line = ser.readline().decode("utf-8", errors="replace").strip()
                    except (serial.SerialException, OSError):
                        raise  # bubble to the reconnect handler below

                    if not line:
                        # Flaky USB-serial adapters (CH340 clones) can drop their
                        # /dev node WITHOUT raising here — readline just times out.
                        # Detect the vanished node and force a reconnect.
                        if not os.path.exists(port):
                            raise OSError(f"serial node {port} disappeared")
                        continue

                    if not line.startswith("UID:"):
                        continue

                    uid = normalize_uid(line[len("UID:"):])

                    # Debounce: ignore the same tag held/re-tapped within a few seconds.
                    now = time.time()
                    if uid == last_uid and (now - last_time) < DEBOUNCE_SECONDS:
                        continue
                    last_uid, last_time = uid, now

                    handle_scan(ser, uid)
        except (serial.SerialException, OSError) as e:
            print(f"! serial connection lost ({e}); reconnecting...\n")
            last_uid, last_time = None, 0.0  # clear debounce across reconnects
            time.sleep(2)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
