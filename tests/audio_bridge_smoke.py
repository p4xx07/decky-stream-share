"""Exercise real Opus RTP pipelines with synthetic audio and a fake sink."""

import asyncio
import os
import tempfile
from pathlib import Path

from relay.audio import AudioBridge


async def main():
    with tempfile.TemporaryDirectory() as root:
        directory = Path(root)
        shim = directory / "gst-launch-1.0"
        shim.write_text(
            "#!/usr/bin/env python3\n"
            "import os, sys\n"
            "args = []\n"
            "for a in sys.argv[1:]:\n"
            "    args.extend(['audiotestsrc', 'is-live=true'] if a == 'pulsesrc' "
            "else ['fakesink'] if a == 'pulsesink' else [a])\n"
            "os.execv('/usr/bin/gst-launch-1.0', ['/usr/bin/gst-launch-1.0'] + args)\n",
            encoding="utf-8",
        )
        shim.chmod(0o755)
        env = os.environ.copy()
        env["PATH"] = f"{directory}:{env['PATH']}"
        packets = []
        bridge = None

        async def loopback(kind, payload):
            packets.append((kind, payload))
            bridge.receive(payload)

        bridge = AudioBridge(directory, env, loopback)
        try:
            await bridge.set_speaker(True)
            await bridge.set_microphone(True)
            for _ in range(30):
                if len(packets) >= 5:
                    break
                await asyncio.sleep(0.1)
            assert len(packets) >= 5, bridge._read_log(bridge.mic_log_path)
            assert all(kind == "A" and payload[0] >> 6 == 2 for kind, payload in packets)
            assert bridge.microphone_enabled and bridge.speaker_enabled
            print(f"Opus RTP bridge sent {len(packets)} packets")
        finally:
            await bridge.stop()


if __name__ == "__main__":
    asyncio.run(main())
