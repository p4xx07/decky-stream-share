# Stream Share for Decky (alpha)

Show your full game beside a friend's game in Steam Deck Gaming Mode. Choose equal side by side, larger local game, or top/bottom. Optional microphone and friend audio start **off**. Both Decks keep their own game and controls; this does not provide shared controls.

This alpha sends JPEG video (about 640×400, at most 10 fps) and Opus microphone audio through a small PC relay over WebSockets. It is **not WebRTC**. Latency and video quality depend on the connection. A PC must stay on while you play.

## Install and try

1. On a Windows, macOS, or Linux PC, download and unzip `pc-relay.zip` from [Releases](https://github.com/p4xx07/decky-stream-share/releases). Follow its short README to start the relay.
2. On **each Deck**, uninstall the old **Stream Share Probe** plugin if installed. In Decky settings → Developer → Install Plugin from URL, enter `http://<PC-LAN-IP>:57322/d.zip`. The same `decky.zip` is also on the [latest alpha release](https://github.com/p4xx07/decky-stream-share/releases).
   Alpha 1 and alpha 2 could leave the room buttons gray. Alpha 3 could leave the local game pane blank. Install this alpha 4 build for both fixes.
3. Start a game on each Deck. In the plugin, enter the **same relay URL**. On one Deck choose **Create room** and tell your friend the six-digit code. On the other choose **Join room** with that code.
4. Choose a layout, press **Start split view** on both Decks, and return to the games. Enable microphone and friend audio separately if wanted. Use **Stop split view** and **Leave room** when finished.

**One Deck test:** Open `http://127.0.0.1:57322/client` on the relay computer. Create a room on the Deck, enter its code in the browser page, and press **Join Deck room**. Press **Send test image** in the browser, then **Start split view** on the Deck. You should see the test image on the Deck and your Deck game in the browser. The browser page can also share the computer screen. The browser test handles video only; microphone audio still needs two Decks.

Try **Check display layer** first if you have not yet tested the overlay. That test closes after 45 seconds. An unconnected live test closes after 90 seconds. A connected live session has a four-hour safety limit and also closes when the plugin unloads.

## Important test status

The display pattern, native JPEG bridge, relay pairing, and frontend build have off-device tests. The display pattern worked on one real Deck. An earlier live capture test failed to connect to PipeWire; the Deck user runtime environment was corrected in v0.0.2 but has **not yet been retested on Deck hardware**. This alpha cannot be claimed to work end to end until both Decks are tested. If live capture fails, copy the error shown in the plugin, including the `PipeWire:` line. If microphone fails, its GStreamer error is shown; voice is optional.

The plugin does not install system packages or change SteamOS settings. Stop the split view from Decky if the display looks wrong. Media passes through your PC relay; a Cloudflare Quick Tunnel also routes it through Cloudflare. Use a trusted relay and share room codes privately.

## Build

Node 22, Python 3.12, and Docker are used for the release build. The native helper is compiled against a SteamOS Holo base image.

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

The renderer uses a [Gamescope external overlay](https://github.com/ValveSoftware/gamescope/blob/master/src/steamcompmgr.cpp) and game capture. It scales both complete 16:10 source frames into their panes; the overlay does not take input focus. Actual Deck compatibility must be checked on hardware.
