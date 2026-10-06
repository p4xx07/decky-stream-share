"""Deck-side connection to a two-person Stream Share relay."""

import asyncio
import json
from collections.abc import Awaitable, Callable
from urllib.parse import urlsplit, urlunsplit

from aiohttp import ClientSession, WSMsgType


MediaHandler = Callable[[str, bytes], Awaitable[None]]


def websocket_url(url: str) -> str:
    parts = urlsplit(url.strip())
    scheme = {"http": "ws", "https": "wss", "ws": "ws", "wss": "wss"}.get(parts.scheme)
    if not scheme or not parts.hostname or parts.username or parts.password:
        raise ValueError("Enter an http(s) or ws(s) relay URL")
    if parts.path not in ("", "/", "/ws") or parts.query or parts.fragment:
        raise ValueError("Enter the relay base URL, without a path or query")
    return urlunsplit((scheme, parts.netloc, "/ws", "", ""))


class RelayConnection:
    def __init__(self, session: ClientSession, ws, code: str, role: str,
                 on_media: MediaHandler | None = None):
        self.session = session
        self.ws = ws
        self.code = code
        self.role = role
        self.on_media = on_media
        self.peer_connected = False
        self.message = "Waiting for another Deck"
        self.closed = False
        self.outgoing = asyncio.Queue(maxsize=8)
        self.sender_task = asyncio.create_task(self._send())
        self.task = asyncio.create_task(self._read())

    async def _send(self) -> None:
        try:
            while True:
                packet = await self.outgoing.get()
                try:
                    await self.ws.send_bytes(packet)
                finally:
                    self.outgoing.task_done()
        except asyncio.CancelledError:
            raise
        except (ConnectionError, RuntimeError, OSError) as exc:
            self.message = f"Relay send failed: {exc}"
            await self.ws.close()

    @classmethod
    async def open(cls, url: str, code: str = "", on_media: MediaHandler | None = None):
        endpoint = websocket_url(url)
        session = ClientSession()
        try:
            ws = await asyncio.wait_for(
                session.ws_connect(endpoint, heartbeat=20, max_msg_size=512 * 1024 + 1), 8
            )
            await ws.send_json({"type": "join", "code": code} if code else {"type": "create"})
            first = await ws.receive(timeout=8)
            if first.type != WSMsgType.TEXT:
                raise RuntimeError("Relay did not return a room")
            reply = json.loads(first.data)
            if reply.get("type") != "room":
                raise RuntimeError(str(reply.get("message", "Relay rejected the room")))
            return cls(session, ws, str(reply["code"]), str(reply["role"]), on_media)
        except Exception:
            await session.close()
            raise

    async def _read(self) -> None:
        try:
            async for packet in self.ws:
                if packet.type == WSMsgType.TEXT:
                    event = json.loads(packet.data)
                    kind = event.get("type")
                    if kind == "peer_joined":
                        self.peer_connected = True
                        self.message = "Friend connected"
                    elif kind == "peer_left":
                        self.peer_connected = False
                        self.message = "Friend disconnected"
                    elif kind == "room_closed":
                        self.message = "Room closed"
                    elif kind == "error":
                        self.message = str(event.get("message", "Relay error"))
                elif packet.type == WSMsgType.BINARY and self.on_media and packet.data:
                    await self.on_media(chr(packet.data[0]), packet.data[1:])
        except (ConnectionError, RuntimeError, ValueError) as exc:
            self.message = f"Relay connection failed: {exc}"
        finally:
            self.closed = True
            self.peer_connected = False
            self.sender_task.cancel()
            try:
                await self.sender_task
            except asyncio.CancelledError:
                pass
            await self.session.close()

    async def send_media(self, kind: str, payload: bytes) -> None:
        if kind not in ("V", "A") or len(payload) > 512 * 1024 - 1:
            raise ValueError("Invalid media packet")
        if self.closed:
            raise RuntimeError("Relay connection is closed")
        if self.outgoing.full():
            self.outgoing.get_nowait()
            self.outgoing.task_done()
        self.outgoing.put_nowait(kind.encode("ascii") + payload)

    async def close(self) -> None:
        self.sender_task.cancel()
        try:
            await self.sender_task
        except asyncio.CancelledError:
            pass
        if not self.closed:
            await self.ws.close()
        if asyncio.current_task() is not self.task:
            try:
                await asyncio.wait_for(self.task, timeout=2)
            except asyncio.TimeoutError:
                self.task.cancel()
                try:
                    await self.task
                except asyncio.CancelledError:
                    pass
        await self.session.close()
