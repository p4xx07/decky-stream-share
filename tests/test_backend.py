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
        with patch.dict(os.environ, {"LD_LIBRARY_PATH": "/tmp/_MEI123", "LD_LIBRARY_PATH_ORIG": "/usr/lib"}):
            env = module.external_program_env()
            self.assertEqual(env["LD_LIBRARY_PATH"], "/usr/lib")
            self.assertNotIn("LD_LIBRARY_PATH_ORIG", env)
            self.assertEqual(os.environ["LD_LIBRARY_PATH"], "/tmp/_MEI123")

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


if __name__ == "__main__":
    unittest.main()
