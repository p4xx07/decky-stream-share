#!/bin/sh
set -eu
Xvfb :99 -screen 0 1280x800x24 >/tmp/stream-share-xvfb.log 2>&1 &
xvfb_pid=$!
trap 'kill "$xvfb_pid" 2>/dev/null || true' EXIT
sleep 2
DISPLAY=:99 python3 tests/media_bridge_smoke.py
