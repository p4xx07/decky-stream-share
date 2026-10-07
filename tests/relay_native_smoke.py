"""Send synthetic frames between two real helpers through the PC relay."""

import asyncio
import os
import subprocess
import tempfile
from pathlib import Path

from aiohttp import web

from relay.client import RelayConnection
from relay.server import create_app


async def main():
    runner = web.AppRunner(create_app())
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    clients = []
    servers = []
    processes = []
    logs = []
    with tempfile.TemporaryDirectory() as root:
        directory = Path(root)
        writers = [None, None]

        async def receive(index, kind, payload):
            writer = writers[index]
            if kind == "V" and writer:
                writer.write(b"V" + len(payload).to_bytes(4, "big") + payload)
                await writer.drain()

        async def handle(index, reader, writer):
            writers[index] = writer
            try:
                while True:
                    header = await reader.readexactly(5)
                    length = int.from_bytes(header[1:], "big")
                    assert header[0] == ord("V") and 0 < length < 512 * 1024
                    payload = await reader.readexactly(length)
                    await clients[index].send_media("V", payload)
            except asyncio.IncompleteReadError:
                pass
            finally:
                writers[index] = None
                writer.close()
                await writer.wait_closed()

        try:
            host = await RelayConnection.open(base, on_media=lambda k, p: receive(0, k, p))
            clients.append(host)
            guest = await RelayConnection.open(base, host.code,
                                               on_media=lambda k, p: receive(1, k, p))
            clients.append(guest)
            for _ in range(100):
                if host.peer_connected and guest.peer_connected:
                    break
                await asyncio.sleep(0.02)
            assert host.peer_connected and guest.peer_connected

            for index in range(2):
                path = directory / f"deck-{index}.sock"
                server = await asyncio.start_unix_server(
                    lambda reader, writer, i=index: handle(i, reader, writer), path=str(path)
                )
                servers.append(server)
                log = (directory / f"deck-{index}.log").open("w+")
                logs.append(log)
                process = subprocess.Popen(
                    ["./bin/stream-share-renderer", "--mode", "synthetic", "--layout", "side",
                     "--ipc", str(path)], stdout=log, stderr=subprocess.STDOUT,
                    env=os.environ.copy(), start_new_session=True,
                )
                processes.append(process)

            for _ in range(150):
                await asyncio.sleep(0.1)
                if all("Received 1 friend frames." in path.read_text(errors="replace")
                       for path in (directory / "deck-0.log", directory / "deck-1.log")):
                    print("Two native helpers exchanged JPEG frames through the relay")
                    break
                if any(process.poll() is not None for process in processes):
                    raise AssertionError("A helper exited: " + "\n".join(
                        path.read_text(errors="replace") for path in
                        (directory / "deck-0.log", directory / "deck-1.log")))
            else:
                raise AssertionError("Timed out waiting for both friend frames: " + "\n".join(
                    path.read_text(errors="replace") for path in
                    (directory / "deck-0.log", directory / "deck-1.log")))
        finally:
            for process in processes:
                if process.poll() is None:
                    process.terminate()
                    try:
                        await asyncio.wait_for(asyncio.to_thread(process.wait), 3)
                    except asyncio.TimeoutError:
                        process.kill()
                        await asyncio.to_thread(process.wait)
            for log in logs:
                log.close()
            for server in servers:
                server.close()
                await server.wait_closed()
            for client in reversed(clients):
                await client.close()
            await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
