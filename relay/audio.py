"""Optional two-way Opus microphone audio over the room relay."""

import asyncio
import shutil
import socket
import subprocess
from collections.abc import Awaitable, Callable
from pathlib import Path


AudioSender = Callable[[str, bytes], Awaitable[None]]


class AudioBridge:
    def __init__(self, runtime_dir: Path, env: dict[str, str], send_media: AudioSender):
        self.runtime_dir = runtime_dir
        self.env = env
        self.send_media = send_media
        self.mic_process = None
        self.speaker_process = None
        self.mic_socket = None
        self.mic_task = None
        self.output_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.speaker_port = None
        self.mic_log_path = runtime_dir / "microphone.log"
        self.speaker_log_path = runtime_dir / "speaker.log"
        self.mic_log = None
        self.speaker_log = None

    @property
    def microphone_enabled(self) -> bool:
        return self.mic_process is not None and self.mic_process.poll() is None

    @property
    def speaker_enabled(self) -> bool:
        return self.speaker_process is not None and self.speaker_process.poll() is None

    def _check_gstreamer(self):
        if not shutil.which("gst-launch-1.0", path=self.env.get("PATH")):
            raise RuntimeError("GStreamer is unavailable on this SteamOS installation")

    async def set_microphone(self, enabled: bool):
        if enabled == self.microphone_enabled:
            return
        await self._stop_microphone()
        if not enabled:
            return
        self._check_gstreamer()
        self.mic_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.mic_socket.bind(("127.0.0.1", 0))
        self.mic_socket.setblocking(False)
        port = self.mic_socket.getsockname()[1]
        self.mic_log = self.mic_log_path.open("w", encoding="utf-8")
        self.mic_process = subprocess.Popen(
            ["gst-launch-1.0", "-q", "pulsesrc", "do-timestamp=true", "!",
             "audioconvert", "!", "audioresample", "!",
             "audio/x-raw,rate=48000,channels=1", "!", "opusenc", "bitrate=24000",
             "!", "rtpopuspay", "pt=96", "!", "udpsink", "host=127.0.0.1",
             f"port={port}", "sync=false"],
            stdin=subprocess.DEVNULL, stdout=self.mic_log,
            stderr=subprocess.STDOUT, env=self.env, start_new_session=True,
        )
        self.mic_task = asyncio.create_task(self._forward_microphone())
        await asyncio.sleep(0.3)
        if self.mic_process.poll() is not None:
            error = self._read_log(self.mic_log_path)
            await self._stop_microphone()
            raise RuntimeError(f"Microphone could not start: {error}")

    async def _forward_microphone(self):
        loop = asyncio.get_running_loop()
        try:
            while self.mic_socket:
                packet, _ = await loop.sock_recvfrom(self.mic_socket, 4096)
                await self.send_media("A", packet)
        except (asyncio.CancelledError, ConnectionError, RuntimeError, OSError):
            pass

    async def set_speaker(self, enabled: bool):
        if enabled == self.speaker_enabled:
            return
        await self._stop_speaker()
        if not enabled:
            return
        self._check_gstreamer()
        reservation = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        reservation.bind(("127.0.0.1", 0))
        self.speaker_port = reservation.getsockname()[1]
        reservation.close()
        self.speaker_log = self.speaker_log_path.open("w", encoding="utf-8")
        self.speaker_process = subprocess.Popen(
            ["gst-launch-1.0", "-q", "udpsrc", f"port={self.speaker_port}",
             "caps=application/x-rtp,media=(string)audio,clock-rate=(int)48000,encoding-name=(string)OPUS,payload=(int)96",
             "!", "rtpjitterbuffer", "latency=60", "!", "rtpopusdepay", "!",
             "opusdec", "!", "audioconvert", "!", "audioresample", "!", "pulsesink"],
            stdin=subprocess.DEVNULL, stdout=self.speaker_log,
            stderr=subprocess.STDOUT, env=self.env, start_new_session=True,
        )
        await asyncio.sleep(0.3)
        if self.speaker_process.poll() is not None:
            error = self._read_log(self.speaker_log_path)
            await self._stop_speaker()
            raise RuntimeError(f"Friend audio could not start: {error}")

    def receive(self, packet: bytes):
        if self.speaker_enabled and self.speaker_port and len(packet) <= 4096:
            self.output_socket.sendto(packet, ("127.0.0.1", self.speaker_port))

    async def _stop_process(self, process):
        if process and process.poll() is None:
            process.terminate()
            try:
                await asyncio.to_thread(process.wait, 3)
            except subprocess.TimeoutExpired:
                process.kill()
                await asyncio.to_thread(process.wait)

    async def _stop_microphone(self):
        if self.mic_task:
            self.mic_task.cancel()
            try:
                await self.mic_task
            except asyncio.CancelledError:
                pass
            self.mic_task = None
        if self.mic_socket:
            self.mic_socket.close()
            self.mic_socket = None
        await self._stop_process(self.mic_process)
        self.mic_process = None
        if self.mic_log:
            self.mic_log.close()
            self.mic_log = None

    async def _stop_speaker(self):
        await self._stop_process(self.speaker_process)
        self.speaker_process = None
        self.speaker_port = None
        if self.speaker_log:
            self.speaker_log.close()
            self.speaker_log = None

    async def stop(self):
        await self._stop_microphone()
        await self._stop_speaker()
        self.output_socket.close()

    @staticmethod
    def _read_log(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8", errors="replace")[-300:] or "GStreamer exited"
        except OSError:
            return "GStreamer exited"
