import unittest
import asyncio

from aiohttp import ClientSession, WSMsgType, web

from relay.server import create_app
from relay.client import RelayConnection, websocket_url


class RelayTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.runner = web.AppRunner(create_app())
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, "127.0.0.1", 0)
        await self.site.start()
        self.port = self.site._server.sockets[0].getsockname()[1]
        self.session = ClientSession()

    async def asyncTearDown(self):
        await self.session.close()
        await self.runner.cleanup()

    async def connect(self):
        return await self.session.ws_connect(f"http://127.0.0.1:{self.port}/ws")

    async def test_two_decks_pair_and_forward_video_and_audio(self):
        host = await self.connect()
        await host.send_json({"type": "create"})
        room = await host.receive_json(timeout=1)
        self.assertEqual(room["role"], "host")
        self.assertEqual(len(room["code"]), 10)

        guest = await self.connect()
        await guest.send_json({"type": "join", "code": room["code"]})
        self.assertEqual((await guest.receive_json(timeout=1))["role"], "guest")
        self.assertEqual((await guest.receive_json(timeout=1))["type"], "peer_joined")
        self.assertEqual((await host.receive_json(timeout=1))["type"], "peer_joined")

        await host.send_bytes(b"V" + b"jpeg-frame")
        video = await guest.receive(timeout=1)
        self.assertEqual(video.type, WSMsgType.BINARY)
        self.assertEqual(video.data, b"Vjpeg-frame")

        await guest.send_bytes(b"A" + b"opus-packet")
        audio = await host.receive(timeout=1)
        self.assertEqual(audio.data, b"Aopus-packet")

        await guest.close()
        self.assertEqual((await host.receive_json(timeout=1))["type"], "peer_left")
        await host.close()

    async def test_wrong_code_is_rejected(self):
        guest = await self.connect()
        await guest.send_json({"type": "join", "code": "INVALID123"})
        self.assertEqual((await guest.receive_json(timeout=1))["type"], "error")
        await guest.close()

    async def test_deck_client_pairs_and_receives_media(self):
        base = f"http://127.0.0.1:{self.port}"
        frames = asyncio.Queue()

        async def on_media(kind, payload):
            await frames.put((kind, payload))

        host = await RelayConnection.open(base)
        guest = await RelayConnection.open(base, host.code, on_media)
        try:
            for _ in range(20):
                if host.peer_connected and guest.peer_connected:
                    break
                await asyncio.sleep(0.01)
            self.assertTrue(host.peer_connected)
            self.assertTrue(guest.peer_connected)
            await host.send_media("V", b"frame")
            self.assertEqual(await asyncio.wait_for(frames.get(), 1), ("V", b"frame"))
        finally:
            await guest.close()
            await host.close()

    def test_url_normalization(self):
        self.assertEqual(websocket_url("https://relay.example"), "wss://relay.example/ws")
        with self.assertRaises(ValueError):
            websocket_url("file:///etc/passwd")
