#!/usr/bin/env bash
#
# Launch the whole Inventory Tracker stack for a demo:
#   1. backend  (FastAPI)            http://<ip>:8000
#   2. frontend (Vite)              http://<ip>:5173
#   3. reader   (RC522 controller)  reads tags, opens pages, writes NDEF
#
# Assumes the three repos sit side by side (the ~/airis layout):
#   ./                                  this repo (InventoryTrackerReader)
#   ../InvetoryTrackerBackend
#   ../InventoryTrackerFront/InvetoryTracker
#
# Override any path or the host IP with env vars:
#   HOST_IP=192.168.0.42 ./run_all.sh
#
# Ctrl+C stops everything.

set -uo pipefail

# Make brew-installed node/python visible even from a bare shell.
export PATH="/opt/homebrew/bin:$PATH"

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="${BACKEND_DIR:-$HERE/../InvetoryTrackerBackend}"
FRONTEND="${FRONTEND_DIR:-$HERE/../InventoryTrackerFront/InvetoryTracker}"

# LAN IP so a phone on the same Wi-Fi can reach the API and the site.
HOST_IP="${HOST_IP:-$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo 127.0.0.1)}"
API_URL="http://$HOST_IP:8000"
SITE_URL="http://$HOST_IP:5173"

# --- sanity checks -----------------------------------------------------------
[ -x "$BACKEND/.venv/bin/uvicorn" ] || { echo "Backend venv missing at $BACKEND/.venv  (run: python3.12 -m venv .venv && .venv/bin/pip install .)"; exit 1; }
[ -x "$HERE/venv/bin/python" ]      || { echo "Reader venv missing at $HERE/venv  (run: python3 -m venv venv && venv/bin/pip install pyserial requests)"; exit 1; }
[ -d "$FRONTEND/node_modules" ]     || { echo "Frontend deps missing at $FRONTEND  (run: npm install)"; exit 1; }

pids=()
cleanup() {
  echo
  echo "Stopping everything..."
  for p in "${pids[@]}"; do kill "$p" 2>/dev/null || true; done
}
trap cleanup EXIT INT TERM

echo "Host IP: $HOST_IP"

# --- 1) backend --------------------------------------------------------------
echo "Starting backend  -> $API_URL   (log: /tmp/it-backend.log)"
( cd "$BACKEND" && .venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 ) > /tmp/it-backend.log 2>&1 &
pids+=($!)

# --- 2) frontend -------------------------------------------------------------
# Pin the API base to the current IP so the phone flow works.
echo "VITE_API_URL=$API_URL" > "$FRONTEND/.env"
echo "Starting frontend -> $SITE_URL   (log: /tmp/it-frontend.log)"
( cd "$FRONTEND" && npm run dev -- --host ) > /tmp/it-frontend.log 2>&1 &
pids+=($!)

# Give the servers a moment to bind.
sleep 4
echo
echo "Open $SITE_URL  (phone: same Wi-Fi)."
echo "Tap a tag below — Ctrl+C stops everything."
echo "--------------------------------------------------------------------"

# --- 3) reader (foreground, so tag scans show live) --------------------------
cd "$HERE"
API_URL="$API_URL" SITE_URL="$SITE_URL" venv/bin/python -u tag_controller.py
