"""Small two-person WebSocket relay for the Steam Deck Stream Share plugin."""

import argparse
import asyncio
import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path

from aiohttp import WSMsgType, web


ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
ROOM_WAIT_SECONDS = 10 * 60
MAX_MEDIA_BYTES = 512 * 1024
ROOMS_KEY = web.AppKey("rooms", dict)


@dataclass
class Peer:
    ws: web.WebSocketResponse
    outgoing: asyncio.Queue[tuple[str, object]] = field(
        default_factory=lambda: asyncio.Queue(maxsize=8)
    )
    sender: asyncio.Task | None = None

    def queue(self, kind: str, payload: object) -> None:
        # Prefer fresh media over building up seconds of delayed video or audio.
        if self.outgoing.full():
            self.outgoing.get_nowait()
            self.outgoing.task_done()
        self.outgoing.put_nowait((kind, payload))


@dataclass
class Room:
    code: str
    host: Peer
    created: float
    guest: Peer | None = None


async def send_queued(peer: Peer) -> None:
    try:
        while not peer.ws.closed:
            kind, payload = await peer.outgoing.get()
            try:
                if kind == "json":
                    await peer.ws.send_json(payload)
                else:
                    await peer.ws.send_bytes(payload)
            finally:
                peer.outgoing.task_done()
    except (ConnectionError, RuntimeError):
        pass


def create_app() -> web.Application:
    app = web.Application()
    rooms: dict[str, Room] = {}
    app[ROOMS_KEY] = rooms

    async def health(_request: web.Request) -> web.Response:
        return web.json_response({"ok": True, "rooms": len(rooms)})

    async def browser_client(_request: web.Request) -> web.FileResponse:
        return web.FileResponse(
            Path(__file__).with_name("client.html"),
            headers={"Cache-Control": "no-store"},
        )

    async def deck_plugin(_request: web.Request) -> web.FileResponse:
        return web.FileResponse(
            Path(__file__).with_name("d.zip"),
            headers={"Cache-Control": "no-store"},
        )

    async def socket(request: web.Request) -> web.WebSocketResponse:
        print(f"WebSocket attempt from {request.remote}", flush=True)
        ws = web.WebSocketResponse(max_msg_size=MAX_MEDIA_BYTES + 1, heartbeat=20)
        await ws.prepare(request)
        room: Room | None = None
        peer: Peer | None = None
        try:
            try:
                first = await asyncio.wait_for(ws.receive_json(), timeout=5)
            except (asyncio.TimeoutError, ValueError, TypeError):
                await ws.send_json({"type": "error", "message": "Send create or join first"})
                return ws
            if not isinstance(first, dict):
                await ws.send_json({"type": "error", "message": "Invalid request"})
                return ws

            action = first.get("type")
            if action == "create":
                if len(rooms) >= 100:
                    await ws.send_json({"type": "error", "message": "Relay is full"})
                    return ws
                code = ""
                while not code or code in rooms:
                    code = "".join(secrets.choice(ALPHABET) for _ in range(6))
                peer = Peer(ws)
                room = Room(code, peer, time.monotonic())
                rooms[code] = room
                print(f"Room created from {request.remote}", flush=True)
                peer.queue("json", {"type": "room", "code": code, "role": "host"})
            elif action == "join":
                code = str(first.get("code", "")).strip().upper()
                room = rooms.get(code)
                if (room is None or room.guest is not None or room.host.ws.closed
                        or time.monotonic() - room.created > ROOM_WAIT_SECONDS):
                    await ws.send_json({"type": "error", "message": "Room unavailable"})
                    return ws
                peer = Peer(ws)
                room.guest = peer
                print(f"Peer joined from {request.remote}", flush=True)
                peer.queue("json", {"type": "room", "code": code, "role": "guest"})
                peer.queue("json", {"type": "peer_joined"})
                room.host.queue("json", {"type": "peer_joined"})
            else:
                await ws.send_json({"type": "error", "message": "Unknown action"})
                return ws

            peer.sender = asyncio.create_task(send_queued(peer))
            async for message in ws:
                if message.type == WSMsgType.BINARY:
                    data = message.data
                    if not data or data[0] not in (ord("V"), ord("A")) or len(data) > MAX_MEDIA_BYTES:
                        peer.queue("json", {"type": "error", "message": "Invalid media packet"})
                        continue
                    other = room.guest if peer is room.host else room.host
                    if other and not other.ws.closed:
                        other.queue("binary", data)
                elif message.type == WSMsgType.TEXT:
                    peer.queue("json", {"type": "error", "message": "Unexpected message"})
                elif message.type == WSMsgType.ERROR:
                    break
        finally:
            if peer and peer.sender:
                peer.sender.cancel()
                try:
                    await peer.sender
                except asyncio.CancelledError:
                    pass
            if room and peer is room.host:
                rooms.pop(room.code, None)
                if room.guest and not room.guest.ws.closed:
                    room.guest.queue("json", {"type": "room_closed"})
                    try:
                        await asyncio.wait_for(room.guest.outgoing.join(), timeout=0.5)
                    except asyncio.TimeoutError:
                        pass
                    await room.guest.ws.close()
            elif room and peer is room.guest:
                room.guest = None
                if not room.host.ws.closed:
                    room.host.queue("json", {"type": "peer_left"})
            await ws.close()
        return ws

    app.router.add_get("/health", health)
    app.router.add_get("/client", browser_client)
    app.router.add_get("/d.zip", deck_plugin)
    app.router.add_get("/ws", socket)
    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Steam Deck Stream Share relay")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=57322)
    args = parser.parse_args()
    web.run_app(create_app(), host=args.host, port=args.port)
