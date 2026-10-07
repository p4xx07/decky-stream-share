#!/usr/bin/env python3
"""ES-DE mGBA launcher. Only an armed session changes RetroArch's settings."""

import os
import selectors
import socket
import subprocess
import sys
from pathlib import Path


DATA = Path.home() / ".local" / "share" / "stream-share"
RUNTIME = Path(os.environ.get("STREAM_SHARE_RUNTIME_DIR", f"/run/user/{os.getuid()}")) / "stream-share"
CONTROL = RUNTIME / "retroarch.sock"
LAYOUTS = {"side", "wide", "stack", "full"}


def main() -> int:
    command = sys.argv[1:]
    if not command:
        print("Stream Share launcher: missing RetroArch command", file=sys.stderr)
        return 2
    if not (DATA / "armed").exists():
        os.execvp(command[0], command)
    RUNTIME.mkdir(mode=0o700, parents=True, exist_ok=True)
    RUNTIME.chmod(0o700)
    try:
        CONTROL.unlink(missing_ok=True)
    except OSError:
        pass
    server = socket.socket(socket.AF_UNIX)
    server.bind(str(CONTROL))
    CONTROL.chmod(0o600)
    server.listen(4)
    server.setblocking(False)
    selector = selectors.DefaultSelector()
    selector.register(server, selectors.EVENT_READ)
    config = DATA / "session.cfg"
    command = [command[0], "--appendconfig", str(config),
               f"--set-shader={DATA / 'full.slangp'}", *command[1:]]
    process = subprocess.Popen(command, stdin=subprocess.PIPE)
    try:
        while process.poll() is None:
            for key, _ in selector.select(timeout=0.2):
                if key.fileobj is not server:
                    continue
                client, _ = server.accept()
                with client:
                    client.settimeout(2)
                    layout = client.recv(64).decode("ascii", errors="ignore").strip()
                    if layout == "STATUS":
                        client.sendall(b"OK\n")
                        continue
                    if layout not in LAYOUTS:
                        client.sendall(b"ERROR invalid layout\n")
                        continue
                    try:
                        assert process.stdin is not None
                        preset = DATA / f"{layout}.slangp"
                        process.stdin.write(f"SET_SHADER {preset}\n".encode())
                        process.stdin.flush()
                        client.sendall(b"OK\n")
                    except (BrokenPipeError, OSError):
                        client.sendall(b"ERROR RetroArch exited\n")
        return process.returncode or 0
    finally:
        selector.close()
        server.close()
        CONTROL.unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(main())
