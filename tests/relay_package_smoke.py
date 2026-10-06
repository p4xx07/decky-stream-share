"""Check that the packaged PC relay serves its matching Deck plugin ZIP."""

import asyncio
import importlib.util
import sys
import tempfile
from pathlib import Path
from zipfile import ZipFile

from aiohttp import ClientSession, web


async def check(relay_package: Path, plugin_package: Path) -> None:
    with tempfile.TemporaryDirectory() as root:
        directory = Path(root)
        with ZipFile(relay_package) as archive:
            archive.extractall(directory)
        server_path = directory / "StreamShareRelay" / "server.py"
        spec = importlib.util.spec_from_file_location("packaged_stream_share_relay", server_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        runner = web.AppRunner(module.create_app())
        await runner.setup()
        try:
            site = web.TCPSite(runner, "127.0.0.1", 0)
            await site.start()
            port = site._server.sockets[0].getsockname()[1]
            async with ClientSession() as session:
                async with session.get(f"http://127.0.0.1:{port}/d.zip") as response:
                    assert response.status == 200, response.status
                    assert await response.read() == plugin_package.read_bytes()
        finally:
            await runner.cleanup()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Usage: relay_package_smoke.py pc-relay.zip decky.zip")
    asyncio.run(check(Path(sys.argv[1]), Path(sys.argv[2])))
    print("Packaged PC relay serves the matching Deck plugin ZIP")
