#!/bin/sh
set -eu
for layout in side wide stack full; do
    ./bin/stream-share-renderer --mode direct-pattern --layout "$layout" \
        >"/tmp/stream-share-alpha-$layout.log" 2>&1 &
    renderer_pid=$!
    sleep 1
    /tmp/overlay-alpha-smoke "$layout"
    kill "$renderer_pid" 2>/dev/null || true
    wait "$renderer_pid"
done
