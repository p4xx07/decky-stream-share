import importlib.util
import logging
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


class BackendTest(unittest.TestCase):
    def test_external_program_uses_original_library_path(self):
        decky = types.SimpleNamespace(logger=logging.getLogger("probe-test"))
        with patch.dict(sys.modules, {"decky": decky}):
            spec = importlib.util.spec_from_file_location("stream_share_probe", Path(__file__).parents[1] / "main.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        with patch.dict(os.environ, {"LD_LIBRARY_PATH": "/tmp/_MEI123", "LD_LIBRARY_PATH_ORIG": "/usr/lib", "XDG_RUNTIME_DIR": "/run/user/0", "PIPEWIRE_REMOTE": "wrong"}):
            env = module.external_program_env()
            self.assertEqual(env["LD_LIBRARY_PATH"], "/usr/lib")
            self.assertNotIn("LD_LIBRARY_PATH_ORIG", env)
            self.assertEqual(os.environ["LD_LIBRARY_PATH"], "/tmp/_MEI123")
            self.assertEqual(env["XDG_RUNTIME_DIR"], f"/run/user/{os.getuid()}")
            self.assertEqual(env["PIPEWIRE_RUNTIME_DIR"], f"/run/user/{os.getuid()}")
            self.assertEqual(env["PIPEWIRE_REMOTE"], "pipewire-0")

    def test_probe_rejects_unknown_mode_without_starting_a_process(self):
        import asyncio

        with tempfile.TemporaryDirectory() as root:
            decky = types.SimpleNamespace(DECKY_PLUGIN_RUNTIME_DIR=root, logger=logging.getLogger("probe-test"))
            with patch.dict(sys.modules, {"decky": decky}):
                spec = importlib.util.spec_from_file_location("stream_share_probe_mode", Path(__file__).parents[1] / "main.py")
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

            async def check():
                plugin = module.Plugin()
                await plugin._main()
                with self.assertRaisesRegex(ValueError, "Unknown probe mode"):
                    await plugin.start_probe("anything")
                self.assertFalse((await plugin.get_status())["running"])

            asyncio.run(check())

    def test_extracted_helper_can_be_made_executable(self):
        decky = types.SimpleNamespace(logger=logging.getLogger("probe-test"))
        with patch.dict(sys.modules, {"decky": decky}):
            spec = importlib.util.spec_from_file_location("stream_share_probe_chmod", Path(__file__).parents[1] / "main.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as root:
            helper = Path(root) / "stream-share-probe"
            helper.write_bytes(b"test")
            helper.chmod(0o644)
            module.ensure_helper_executable(helper)
            self.assertTrue(os.access(helper, os.X_OK))

    def test_invalid_layout_is_rejected(self):
        import asyncio

        with tempfile.TemporaryDirectory() as root:
            decky = types.SimpleNamespace(DECKY_PLUGIN_RUNTIME_DIR=root, logger=logging.getLogger("probe-test"))
            with patch.dict(sys.modules, {"decky": decky}):
                spec = importlib.util.spec_from_file_location("stream_share_probe_layout", Path(__file__).parents[1] / "main.py")
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

            async def check():
                plugin = module.Plugin()
                await plugin._main()
                with self.assertRaisesRegex(ValueError, "Unknown split-view layout"):
                    await plugin.set_layout("cropped")
                self.assertEqual((await plugin.get_status())["layout"], "side")
                self.assertEqual((await plugin.set_layout("stack"))["layout"], "stack")

            asyncio.run(check())


if __name__ == "__main__":
    unittest.main()
