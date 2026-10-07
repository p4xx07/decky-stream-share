"""User-level Decky control for the Stream Share split view."""

import asyncio
import os
import shutil
import stat
import subprocess
import traceback
from pathlib import Path

import decky
from relay.audio import AudioBridge
from relay.client import RelayConnection


def load_gba_setup():
    """Keep an optional GBA integration failure from taking down the whole backend."""
    from retroarch import setup
    return setup


def external_program_env() -> dict[str, str]:
    """Use the Deck user's PipeWire socket and system libraries."""
    env = os.environ.copy()
    original = env.pop("LD_LIBRARY_PATH_ORIG", None)
    if original:
        env["LD_LIBRARY_PATH"] = original
    else:
        env.pop("LD_LIBRARY_PATH", None)
    env.pop("LD_PRELOAD", None)
    runtime_dir = f"/run/user/{os.getuid()}"
    env["XDG_RUNTIME_DIR"] = runtime_dir
    env["PIPEWIRE_RUNTIME_DIR"] = runtime_dir
    env["PIPEWIRE_REMOTE"] = "pipewire-0"
    env["PULSE_SERVER"] = f"unix:{runtime_dir}/pulse/native"
    env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path={runtime_dir}/bus"
    env["DISPLAY"] = ":0"
    return env


def ensure_helper_executable(helper: Path) -> None:
    if not helper.is_file():
        raise RuntimeError("Renderer is missing from this plugin ZIP")
    if not os.access(helper, os.X_OK):
        try:
            helper.chmod(stat.S_IMODE(helper.stat().st_mode) | stat.S_IXUSR)
        except OSError as exc:
            raise RuntimeError("Renderer could not be made executable") from exc
    if not os.access(helper, os.X_OK):
        raise RuntimeError("Renderer is not executable")


class Plugin:
    async def _main(self):
        self.runtime_dir = Path(decky.DECKY_PLUGIN_RUNTIME_DIR)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.runtime_dir / "renderer.log"
        self.process = None
        self.log_handle = None
        self.mode = ""
        self.layout = "side"
        settings_dir = Path(getattr(decky, "DECKY_PLUGIN_SETTINGS_DIR", self.runtime_dir))
        settings_dir.mkdir(parents=True, exist_ok=True)
        self.relay_url_path = settings_dir / "relay_url.txt"
        try:
            self.relay_url = self.relay_url_path.read_text(encoding="utf-8").strip()
        except OSError:
            self.relay_url = ""
        self.connection = None
        self.audio = None
        self.media_server = None
        self.media_writer = None
        self.media_socket_path = self.runtime_dir / f"media-{os.getpid()}.sock"
        self.sent_frames = 0
        self.received_frames = 0
        self.capture_diagnostic = ""
        self.gba_status_error = ""
        self.gba_diagnostic = ""
        decky.logger.info("Stream Share backend ready (%s)", os.environ.get("DECKY_PLUGIN_VERSION", "unknown version"))

    async def _unload(self):
        await self.stop_room()
        await self.stop_view()

    async def start_room(self, relay_url: str, join_code: str = ""):
        if self.connection and not self.connection.closed:
            raise RuntimeError("Already connected to a room")
        if self.audio:
            await self.audio.stop()
            self.audio = None
        self.connection = await RelayConnection.open(
            relay_url, join_code.strip().upper(), self._receive_media
        )
        try:
            self.audio = AudioBridge(self.runtime_dir, external_program_env(), self._send_audio)
        except Exception:
            await self.connection.close()
            self.connection = None
            raise
        self.relay_url = relay_url.strip()
        try:
            self.relay_url_path.write_text(self.relay_url, encoding="utf-8")
        except OSError:
            # A settings write failure must not hide an established room.
            pass
        return await self.get_status()

    async def stop_room(self):
        if self.media_server:
            await self.stop_view()
        if self.audio:
            await self.audio.stop()
            self.audio = None
        if self.connection:
            await self.connection.close()
            self.connection = None
        return await self.get_status()

    async def _send_audio(self, kind: str, payload: bytes):
        if self.connection and self.connection.peer_connected:
            await self.connection.send_media(kind, payload)

    async def set_microphone(self, enabled: bool):
        if not self.connection or self.connection.closed or not self.audio:
            raise RuntimeError("Connect to a room first")
        await self.audio.set_microphone(enabled)
        return await self.get_status()

    async def set_speaker(self, enabled: bool):
        if not self.connection or self.connection.closed or not self.audio:
            raise RuntimeError("Connect to a room first")
        await self.audio.set_speaker(enabled)
        return await self.get_status()

    async def _receive_media(self, kind: str, payload: bytes):
        if kind == "A":
            if self.audio:
                try:
                    self.audio.receive(payload)
                except OSError:
                    pass
            return
        if kind != "V" or not self.media_writer:
            return
        if self.media_writer.transport.get_write_buffer_size() > 512 * 1024:
            return
        try:
            self.media_writer.write(b"V" + len(payload).to_bytes(4, "big") + payload)
            await self.media_writer.drain()
            self.received_frames += 1
        except (ConnectionError, RuntimeError, OSError):
            pass

    async def _handle_media(self, reader: asyncio.StreamReader,
                            writer: asyncio.StreamWriter):
        if self.media_writer:
            writer.close()
            await writer.wait_closed()
            return
        self.media_writer = writer
        try:
            while True:
                header = await reader.readexactly(5)
                length = int.from_bytes(header[1:], "big")
                if header[0] != ord("V") or not (0 < length <= 512 * 1024 - 1):
                    break
                payload = await reader.readexactly(length)
                if self.connection and self.connection.peer_connected:
                    await self.connection.send_media("V", payload)
                    self.sent_frames += 1
        except (asyncio.IncompleteReadError, ConnectionError, RuntimeError, OSError):
            pass
        finally:
            if self.media_writer is writer:
                self.media_writer = None
            writer.close()
            await writer.wait_closed()

    async def start_view(self, mode: str):
        if mode not in ("pattern", "live", "direct"):
            raise ValueError("Unknown view mode")
        if self.process and self.process.poll() is None:
            raise RuntimeError("Split view is already running")
        if self.process or self.media_server:
            await self.stop_view()
        helper = Path(__file__).resolve().parent / "bin" / "stream-share-renderer"
        ensure_helper_executable(helper)
        if mode in ("live", "direct") and not shutil.which("gst-launch-1.0"):
            raise RuntimeError("GStreamer is unavailable on this SteamOS installation")
        if self.log_handle:
            self.log_handle.close()
        self.log_handle = self.log_path.open("w", encoding="utf-8")
        self.mode = mode
        self.sent_frames = 0
        self.received_frames = 0
        self.capture_diagnostic = ""
        env = external_program_env()
        if mode in ("live", "direct"):
            socket = Path(env["PIPEWIRE_RUNTIME_DIR"]) / env["PIPEWIRE_REMOTE"]
            self.capture_diagnostic = (
                f"PipeWire: uid={os.getuid()}, socket={socket}, "
                f"socket_found={socket.is_socket()}"
            )
            self.log_handle.write(self.capture_diagnostic + "\n")
            self.log_handle.flush()
        args = [str(helper), "--mode", mode, "--layout", self.layout]
        gba_setup = None
        try:
            if mode in ("live", "direct") and self.connection and not self.connection.closed:
                self.media_socket_path.unlink(missing_ok=True)
                self.media_server = await asyncio.start_unix_server(
                    self._handle_media, path=str(self.media_socket_path)
                )
                self.media_socket_path.chmod(0o600)
                args += ["--ipc", str(self.media_socket_path)]
            if mode == "direct":
                gba_setup = load_gba_setup()
                await asyncio.to_thread(gba_setup.set_layout, self.layout)
            self.process = subprocess.Popen(
                args,
                stdin=subprocess.DEVNULL,
                stdout=self.log_handle,
                stderr=subprocess.STDOUT,
                env=env,
                start_new_session=True,
            )
        except Exception:
            if self.media_server:
                self.media_server.close()
                await self.media_server.wait_closed()
                self.media_server = None
            self.media_socket_path.unlink(missing_ok=True)
            if gba_setup is not None and gba_setup.active():
                try:
                    await asyncio.to_thread(gba_setup.set_layout, "full")
                except RuntimeError:
                    pass
            self.mode = ""
            self.log_handle.close()
            self.log_handle = None
            raise
        await asyncio.sleep(0.5)
        if gba_setup is not None and self.process.poll() is not None and gba_setup.active():
            try:
                await asyncio.to_thread(gba_setup.set_layout, "full")
            except RuntimeError:
                pass
        return await self.get_status()

    async def set_layout(self, layout: str):
        if layout not in ("side", "wide", "stack", "full"):
            raise ValueError("Unknown split-view layout")
        if self.process and self.process.poll() is None:
            if self.mode != "direct":
                raise RuntimeError("Stop split view before changing its layout")
            await self.stop_view()
            self.layout = layout
            return await self.start_view("direct")
        self.layout = layout
        return await self.get_status()

    async def prepare_gba(self):
        decky.logger.info("GBA setup started")
        try:
            gba_setup = load_gba_setup()
            message = await asyncio.to_thread(gba_setup.install)
        except Exception:
            self.gba_diagnostic = traceback.format_exc()[-1600:]
            decky.logger.exception("GBA setup failed")
            raise
        self.gba_diagnostic = ""
        decky.logger.info("GBA setup completed")
        status = await self.get_status()
        status["setup_message"] = message
        return status

    async def disable_gba(self):
        gba_setup = load_gba_setup()
        message = await asyncio.to_thread(gba_setup.disarm)
        status = await self.get_status()
        status["setup_message"] = message
        return status

    async def restore_gba(self):
        gba_setup = load_gba_setup()
        if self.process and self.process.poll() is None:
            await self.stop_view()
        message = await asyncio.to_thread(gba_setup.restore_esde)
        status = await self.get_status()
        status["setup_message"] = message
        return status

    async def stop_view(self):
        was_direct = self.mode == "direct"
        restore_error = ""
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                await asyncio.to_thread(self.process.wait, 3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                await asyncio.to_thread(self.process.wait)
        self.process = None
        self.mode = ""
        if was_direct:
            try:
                gba_setup = load_gba_setup()
                if gba_setup.active():
                    await asyncio.to_thread(gba_setup.set_layout, "full")
            except Exception as exc:
                restore_error = str(exc)
        if self.media_writer:
            self.media_writer.close()
            await self.media_writer.wait_closed()
            self.media_writer = None
        if self.media_server:
            self.media_server.close()
            await self.media_server.wait_closed()
            self.media_server = None
            self.media_socket_path.unlink(missing_ok=True)
        if self.log_handle:
            self.log_handle.close()
            self.log_handle = None
        status = await self.get_status()
        if restore_error:
            status["message"] = f"View stopped, but RetroArch did not restore full screen: {restore_error}"
        return status

    async def get_status(self):
        running = self.process is not None and self.process.poll() is None
        exit_code = None if self.process is None else self.process.poll()
        if running:
            message = f"Split view running ({self.layout}). Return to the game."
        elif exit_code is not None and exit_code != 0:
            message = f"Split view stopped with exit code {exit_code}. Open Show logs for details."
        else:
            message = "Split view stopped."
        try:
            log = self.log_path.read_text(encoding="utf-8", errors="replace")[-800:]
        except OSError:
            log = ""
        connection = self.connection
        try:
            gba_setup = load_gba_setup()
            gba_prepared = (gba_setup.DATA / "armed").exists()
            gba_running = gba_setup.active()
            gba_message = ""
            self.gba_status_error = ""
        except Exception as exc:
            gba_prepared = False
            gba_running = False
            gba_message = f"GBA integration unavailable: {type(exc).__name__}: {exc}"
            if gba_message != self.gba_status_error:
                self.gba_diagnostic = traceback.format_exc()[-1600:]
                decky.logger.exception("GBA status check failed")
                self.gba_status_error = gba_message
        return {"running": running, "mode": self.mode, "layout": self.layout,
                "backend_version": os.environ.get("DECKY_PLUGIN_VERSION", "unknown"),
                "message": message, "log": log,
                "capture_diagnostic": self.capture_diagnostic,
                "relay_url": self.relay_url,
                "room_connected": bool(connection and not connection.closed),
                "room_code": connection.code if connection and not connection.closed else "",
                "peer_connected": bool(connection and connection.peer_connected),
                "relay_message": connection.message if connection else "Not connected",
                "sent_frames": self.sent_frames, "received_frames": self.received_frames,
                "microphone_enabled": bool(self.audio and self.audio.microphone_enabled),
                "speaker_enabled": bool(self.audio and self.audio.speaker_enabled),
                "gba_prepared": gba_prepared,
                "gba_running": gba_running,
                "setup_message": gba_message,
                "gba_diagnostic": self.gba_diagnostic}
