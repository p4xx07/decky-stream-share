# Stream Share Probe

This is a **display feasibility test**, not the finished friend-streaming plugin. It has no networking or microphone yet. In Gaming Mode it tries to show your entire running game, scaled into the left half, beside a right-hand test pane. It does not change SteamOS settings, install system packages, or request root access.

## Test on a Steam Deck

1. Install the experimental `StreamShareProbe-0.0.2.zip` through Decky settings → Developer → Install Plugin from URL or ZIP.
2. Start EmulationStation and a game. In **Stream Share Probe**, press **Check display layer**. Return to the game and verify the test layout appears, that the controller still operates the game, and that the `...` menu still opens. Stop the test.
3. Press **Live game view**. Return to the game. Its *complete* image should appear in the left pane with no recursive copy of the test pane. The right pane stands in for a friend's video. Stop the test from Decky.

If live capture fails, open the plugin again and read its log. It reports which Deck-user PipeWire socket it tried and whether that socket exists. The Deck must provide `gst-launch-1.0` with `pipewiresrc`; the probe reports a missing command rather than changing SteamOS. A test also stops when Decky unloads the plugin.
The display test closes itself after 45 seconds; live capture closes after 90 seconds. You can also stop either test from Decky.

Please report whether the display appeared, whether all game edges remained visible, whether controls worked, the number of captured frames shown in the log, and your SteamOS/Decky versions. The test has to pass on actual Deck hardware before adding WebRTC, voice, room codes, or layout choices.

## Build

The frontend uses Node 22. The native helper is built against the SteamOS Holo image to avoid newer Linux C++ runtime requirements.

```sh
npm ci
npm run typecheck
npm run build
docker build -f backend/Dockerfile -t stream-share-probe-build .
docker run --rm -v "$PWD":/work -w /work stream-share-probe-build sh backend/build.sh
python3 package_plugin.py
```

The source for the helper is in `backend/probe.cpp`. Its only runtime system dependencies are X11/Xext and a GStreamer executable for live capture. The design uses [Gamescope's external overlay window](https://github.com/ValveSoftware/gamescope/blob/master/src/steamcompmgr.cpp) and its [PipeWire game capture](https://github.com/ValveSoftware/gamescope/blob/master/src/steamcompmgr.cpp); compatibility with a particular Deck still needs the test above.
