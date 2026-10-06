"""User-level Decky control for the split-view display probe."""

import asyncio
import os
import shutil
import stat
import subprocess
from pathlib import Path

import decky


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
    env["DISPLAY"] = ":0"
    return env


def ensure_helper_executable(helper: Path) -> None:
    if not helper.is_file():
        raise RuntimeError("Probe binary is missing from this plugin ZIP")
    if not os.access(helper, os.X_OK):
        try:
            helper.chmod(stat.S_IMODE(helper.stat().st_mode) | stat.S_IXUSR)
        except OSError as exc:
            raise RuntimeError("Probe binary could not be made executable") from exc
    if not os.access(helper, os.X_OK):
        raise RuntimeError("Probe binary is not executable")


class Plugin:
    async def _main(self):
        self.runtime_dir = Path(decky.DECKY_PLUGIN_RUNTIME_DIR)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.runtime_dir / "probe.log"
        self.process = None
        self.log_handle = None
        self.mode = ""

    async def _unload(self):
        await self.stop_probe()

    async def start_probe(self, mode: str):
        if mode not in ("pattern", "live"):
            raise ValueError("Unknown probe mode")
        if self.process and self.process.poll() is None:
            raise RuntimeError("A display test is already running")
        helper = Path(__file__).resolve().parent / "bin" / "stream-share-probe"
        ensure_helper_executable(helper)
        if mode == "live" and not shutil.which("gst-launch-1.0"):
            raise RuntimeError("GStreamer is unavailable on this SteamOS installation")
        if self.log_handle:
            self.log_handle.close()
        self.log_handle = self.log_path.open("w", encoding="utf-8")
        self.mode = mode
        env = external_program_env()
        if mode == "live":
            socket = Path(env["PIPEWIRE_RUNTIME_DIR"]) / env["PIPEWIRE_REMOTE"]
            self.log_handle.write(
                f"PipeWire: uid={os.getuid()}, socket={socket}, "
                f"socket_found={socket.is_socket()}\n"
            )
            self.log_handle.flush()
        self.process = subprocess.Popen(
            [str(helper), "--mode", mode],
            stdin=subprocess.DEVNULL,
            stdout=self.log_handle,
            stderr=subprocess.STDOUT,
            env=env,
            start_new_session=True,
        )
        await asyncio.sleep(0.5)
        return await self.get_status()

    async def stop_probe(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                await asyncio.to_thread(self.process.wait, 3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                await asyncio.to_thread(self.process.wait)
        self.process = None
        self.mode = ""
        if self.log_handle:
            self.log_handle.close()
            self.log_handle = None
        return await self.get_status()

    async def get_status(self):
        running = self.process is not None and self.process.poll() is None
        exit_code = None if self.process is None else self.process.poll()
        if running:
            message = f"{self.mode.title()} display test running. Return to the game to inspect it."
        elif exit_code is not None and exit_code != 0:
            message = f"Display test stopped with exit code {exit_code}. See details below."
        else:
            message = "Display test stopped."
        try:
            log = self.log_path.read_text(encoding="utf-8", errors="replace")[-800:]
        except OSError:
            log = ""
        return {"running": running, "mode": self.mode, "message": message, "log": log}
