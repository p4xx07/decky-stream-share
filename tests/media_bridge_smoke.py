"""Exercise JPEG output and friend-frame input under a virtual X display."""

import os
import socket
import subprocess
import tempfile
import time
from pathlib import Path


def read_exact(connection: socket.socket, length: int) -> bytes:
    result = bytearray()
    while len(result) < length:
        chunk = connection.recv(length - len(result))
        if not chunk:
            raise RuntimeError("Media helper closed the socket early")
        result.extend(chunk)
    return bytes(result)


def check_mode(mode: str):
    with tempfile.TemporaryDirectory() as root:
        path = str(Path(root) / "media.sock")
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        listener.bind(path)
        listener.listen(1)
        listener.settimeout(8)
        process = subprocess.Popen(
            ["./bin/stream-share-renderer", "--mode", mode, "--layout", "side",
             "--ipc", path],
            env=os.environ.copy(), stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            text=True,
        )
        try:
            connection, _ = listener.accept()
            with connection:
                connection.settimeout(8)
                header = read_exact(connection, 5)
                assert header[0:1] == b"V", header
                length = int.from_bytes(header[1:], "big")
                assert 0 < length < 512 * 1024, length
                jpeg = read_exact(connection, length)
                assert jpeg.startswith(b"\xff\xd8") and jpeg.endswith(b"\xff\xd9")
                connection.sendall(header + jpeg)
                time.sleep(2)
        finally:
            process.terminate()
            _, errors = process.communicate(timeout=5)
            listener.close()
        assert process.returncode == 0, errors
        assert "Received 1 friend frames" in errors, errors
        if mode == "synthetic":
            assert "Displayed 10 local game frames" in errors, errors
        else:
            assert "Displayed 10 local game frames" not in errors, errors
        print(f"JPEG bridge sent and received a friend frame in {mode} mode")


def main():
    for mode in ("synthetic", "direct-test"):
        check_mode(mode)


if __name__ == "__main__":
    main()
