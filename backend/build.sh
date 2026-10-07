#!/bin/sh
set -eu
mkdir -p bin
g++ -std=c++17 -O2 -Wall -Wextra -pthread -Ibackend/vendor backend/renderer.cpp backend/media_bridge.cpp -o bin/stream-share-renderer -lX11 -lXext -lXrender
