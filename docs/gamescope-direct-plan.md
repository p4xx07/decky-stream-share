# Direct game pane prototype

The current Decky overlay draws a captured copy of the local game. It now wakes when a captured frame arrives and can draw up to 30 fps, but capture and CPU copies still add work and delay while a demanding game is running.

## Proposed route

1. Prototype a user-owned Gamescope fork launched **per game** in nested mode. Do not replace SteamOS's running Gamescope or modify system files.
2. In that compositor, place the focused game's existing GPU texture in the selected local pane. Clip it to that pane, preserve aspect ratio, and map pointer input through the same transform.
3. Draw only the decoded friend video and black unused area in the other pane. The Decky plugin controls layout and audio over a local socket.
4. Capture the game before the split composition for outbound streaming, so the friend receives the full game without the local layout or a recursive overlay.

Gamescope currently paints the focused game as its base layer and an external overlay as a separate layer. Its public overlay mechanism does not expose a transform for the base game plane. The relevant path is [`paint_all` in Gamescope](https://github.com/ValveSoftware/gamescope/blob/master/src/steamcompmgr.cpp). A nested fork is a feasibility proposal, not yet a working Deck build.

## Gates before Deck installation

- Build the fork as an unprivileged binary in a SteamOS-compatible container.
- Use a moving test game and a synthetic friend stream under a virtual display. Verify both pane geometry and gamepad/pointer input.
- Measure frame time against the same game without the wrapper. If nested presentation adds noticeable latency or fails to launch common games, stop this route.
- Only then offer an optional per-game launch command on Deck. Exiting it must restore the normal game session without changing SteamOS files.
