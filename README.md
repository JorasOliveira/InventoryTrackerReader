# Inventory Tracker — RFID Reader

The desk-side hardware + software for the Inventory Tracker project: an **Arduino
+ RC522** reads **NTAG215** tags, and a Python controller resolves each tag
against the [backend API](https://github.com/GuilhermeLopesBertacini/InvetoryTrackerBackend)
and opens the matching page on the [frontend](https://github.com/DiogoWolfie/InventoryTrackerFront).

## Flow

```
tap tag → read UID → GET /tags/by-uid/{uid}
            ├─ exists → open  {SITE_URL}/t/{uid}   (edit page)
            └─ new    → write NDEF URL onto the tag, open the create page
```

## Hardware (RC522 → Arduino Uno)

| RC522 | Arduino |
|-------|---------|
| SDA/SS | D10 |
| SCK | D13 |
| MOSI | D11 |
| MISO | D12 |
| RST | D9 |
| 3.3V | 3.3V (**not 5V**) |
| GND | GND |

## Firmware

`rfid-reader.ino` — reads tag UIDs and prints `UID:...` over serial; accepts
`WRITE:<url>` to store an NDEF URI record on the tag. Needs the **MFRC522**
library (Arduino IDE → Library Manager). Upload at 9600 baud.

## Python

```bash
python3 -m venv venv
venv/bin/pip install pyserial requests
```

| Script | Purpose |
|--------|---------|
| `tag_controller.py` | main loop: read → check API → write NDEF / open browser. Auto-reconnects if the serial port drops. |
| `write_test.py` | write a single URL to a tag (standalone test) |
| `continuous_writer.py` | write a fixed URL to every new tag, dedupe by UID |
| `read_uids.py` / `save_uids.py` | early read-only loggers |

Run the controller (override defaults with env vars as needed):

```bash
API_URL=http://<host>:8000 SITE_URL=http://<host>:5173 \
  venv/bin/python tag_controller.py
```

> Note: only one program can hold the serial port — close the Arduino IDE's
> Serial Monitor before running the Python scripts.
