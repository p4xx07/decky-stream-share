"""Load the packaged backend with Decky's documented py_modules import path."""

import asyncio
import importlib.util
import logging
import os
import sys
import tempfile
import types
from pathlib import Path
from zipfile import ZipFile


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: decky_import_smoke.py plugin.zip")
    package = Path(sys.argv[1]).resolve()
    repo_root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as root:
        directory = Path(root)
        with ZipFile(package) as archive:
            archive.extractall(directory)
        plugin_dir = directory / "Stream Share"
        module_dir = plugin_dir / "py_modules"
        decky = types.SimpleNamespace(
            DECKY_PLUGIN_RUNTIME_DIR=str(directory / "runtime"),
            DECKY_PLUGIN_SETTINGS_DIR=str(directory / "settings"),
            logger=logging.getLogger("decky-import-smoke"),
        )
        sys.modules["decky"] = decky
        os.chdir(directory)
        sys.path = [entry for entry in sys.path if entry and Path(entry).resolve() != repo_root]
        sys.path.append(str(module_dir))
        spec = importlib.util.spec_from_file_location("decky_plugin_test", plugin_dir / "main.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        async def check():
            plugin = module.Plugin()
            await plugin._main()
            status = await plugin.get_status()
            assert status["room_connected"] is False
            await plugin._unload()

        asyncio.run(check())
        print("Packaged Decky backend imports and starts with py_modules only")


if __name__ == "__main__":
    main()
