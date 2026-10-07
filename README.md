# Stream Share for Decky (alpha 8 prerelease)

Play your own EmuDeck GBA game on the left and see your friend's stream on the right, in Steam Deck Gaming Mode. Side, wide, stack, and full layouts are available from Decky. Microphone and friend audio are optional and start off. A PC or Mac runs the relay; the six-digit room code pairs two players.

## Install and play

1. Unzip `StreamShareRelay-0.1.0-alpha.8.zip` on a Windows, macOS, or Linux computer. Start it using [the relay guide](relay/README.md). Keep the terminal open.
2. With the computer and Deck on the same Wi-Fi, install `http://<computer-IP>:57322/d.zip` on each Deck in Decky → Settings → Developer → Install Plugin from URL.
3. In Stream Share, press **Set up GBA sharing** once. Restart ES-DE completely. Launch Pokémon Emerald using **mGBA** (RetroArch), then confirm **GBA game detected** in Decky.
4. Set **PC relay URL** to `http://<computer-IP>:57322` on both Decks. Create a room on one and join its six-digit code on the other. Select a layout and press **Start GBA split view**.

For a one-Deck test, open `http://127.0.0.1:57322/client` on the relay computer, join the Deck's room, and send a test image. The browser client can receive Deck video and send its screen. Browser microphone audio is not implemented.

**Stop split view** returns GBA to full screen. **Disable GBA sharing for next launch** and **Restore ES-DE GBA settings** are under **Show logs**. Setup backs up the ES-DE custom systems file and changes no SteamOS system files.

If setup fails, photograph the error beside the setup button and open **Show logs** for the UI/backend versions and last action. If the backend says **no response**, use Decky Settings → Plugins → Stream Share → ⋯ → **Reload**. The plugin's full traceback is in the newest file under `~/homebrew/logs/Stream Share/` if needed.

## Test status

An earlier alpha paired one Deck and a Mac. The direct GBA path in this prerelease has passed automated tests and a SteamOS-targeted build, but **has not yet been verified on a Steam Deck**. Gamescope overlay blending, live RetroArch layout, two-Deck audio, and cross-network latency still require real-device tests.

Video currently uses JPEG over WebSockets at up to 10 fps; it is not WebRTC. The local game is rendered directly by RetroArch in the new GBA path, while the friend's stream may still be choppy. The legacy captured view for other games remains available under **Show logs**.

## Build

```sh
npm ci
npm run typecheck
npm run build
python3 -m pip install -r relay/requirements.txt
python3 -m unittest discover -s tests -v
docker build -f backend/Dockerfile -t stream-share-build .
docker run --rm -v "$PWD":/work -w /work stream-share-build sh backend/build.sh
python3 package_plugin.py
```

See [the direct GBA test gate](docs/gamescope-direct-plan.md) for the hardware checks.
