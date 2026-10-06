#!/bin/sh
set -eu
mkdir -p bin
g++ -std=c++17 -O2 -Wall -Wextra -pthread backend/probe.cpp -o bin/stream-share-probe -lX11 -lXext
