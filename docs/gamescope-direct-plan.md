# Direct GBA pane: implementation and Deck gate

The alpha 7 candidate adds a RetroArch mGBA path. A session-only Slang shader places the live game in the selected pane. The Gamescope external overlay uses an ARGB window that is transparent over the game and opaque over the friend pane. Outbound PipeWire capture crops the local pane before JPEG encoding. RetroArch keeps game input and presentation; Stream Share never sends controller input to the friend.

Decky installs a GBA command in ES-DE's user `custom_systems/es_systems.xml` and backs up the original file. The command launches a small user-owned wrapper. When GBA sharing is armed, the wrapper gives RetroArch a session-only config and writes shader changes to its stdin over a private Unix socket. It does not turn on RetroArch's public network command interface. Disabling sharing lets later GBA launches use the normal RetroArch command; **Restore ES-DE GBA settings** restores the exact original file if it has not been edited since setup.

## Hardware gate

1. Install the candidate ZIP on one Deck. Press **Set up GBA sharing**, fully restart ES-DE, and launch Pokémon Emerald with the **mGBA RetroArch** emulator.
2. Confirm **Stream Share GBA game detected** appears. Join the Mac browser client, send its test image, and start **GBA split view**.
3. Check that the local game is in the left pane, responsive, and receives controls. Change Side → Wide → Stack → Full during play. Check that stopping the view returns the game to full screen.
4. Check the Mac receives the complete game, not the friend overlay or a recursively split frame. Measure local input feel against ordinary RetroArch launch.
5. Only after that, repeat with two Decks, microphone and speaker enabled separately, then test a cross-network relay. Do not release this candidate as proven before these checks.

Virtual X, shader compiler, launcher, package, and relay tests catch syntax, protocol, and process failures. They cannot establish Gamescope's ARGB blending or RetroArch's viewport behavior on a real Deck.
