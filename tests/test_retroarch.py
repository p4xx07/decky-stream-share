import os
import subprocess
import sys
import tempfile
import time
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

from retroarch import setup


ROOT = Path(__file__).parents[1]


class RetroArchSetupTest(unittest.TestCase):
    def test_install_creates_and_restore_removes_new_custom_file(self):
        with tempfile.TemporaryDirectory() as root:
            home = Path(root)
            custom = home / "ES-DE" / "custom_systems" / "es_systems.xml"
            (home / "ES-DE").mkdir()
            with patch.object(setup, "DATA", home / ".local/share/stream-share"), \
                 patch.object(setup, "CUSTOM", custom):
                setup.install()
                gba = ET.parse(custom).getroot().find("system")
                self.assertEqual(gba.findtext("name"), "gba")
                self.assertIn("launch-gba", gba.find("command").text)
                setup.restore_esde()
                self.assertFalse(custom.exists())

    def test_install_and_restore_preserve_other_systems(self):
        with tempfile.TemporaryDirectory() as root:
            home = Path(root)
            custom = home / "ES-DE" / "custom_systems" / "es_systems.xml"
            custom.parent.mkdir(parents=True)
            original = b'''<?xml version="1.0"?>
<systemList>
  <!-- keep me -->
  <system><name>gba</name><fullname>My GBA</fullname><path>%ROMPATH%/gba</path>
    <extension>.gba .GBA</extension>
    <command label="mGBA">original command</command>
    <command label="mGBA (Standalone)">standalone command</command>
    <platform>gba</platform><theme>gba</theme></system>
  <system><name>nes</name><fullname>NES</fullname></system>
</systemList>'''
            custom.write_bytes(original)
            with patch.object(setup, "DATA", home / ".local/share/stream-share"), \
                 patch.object(setup, "CUSTOM", custom):
                setup.install()
                self.assertTrue((setup.DATA / "armed").exists())
                self.assertIn(b"keep me", custom.read_bytes())
                self.assertIn(b"standalone command", custom.read_bytes())
                self.assertIn(b"launch-gba", custom.read_bytes())
                self.assertEqual(len(ET.parse(custom).getroot().findall("system")), 2)
                setup.install()
                self.assertEqual(setup.restore_esde(),
                                 "Original ES-DE GBA configuration restored. Restart ES-DE.")
                self.assertEqual(custom.read_bytes(), original)
                self.assertFalse((setup.DATA / "armed").exists())

    def test_refuses_to_overwrite_later_esde_edits(self):
        with tempfile.TemporaryDirectory() as root:
            home = Path(root)
            custom = home / "ES-DE" / "custom_systems" / "es_systems.xml"
            custom.parent.mkdir(parents=True)
            custom.write_text("<systemList/>")
            with patch.object(setup, "DATA", home / ".local/share/stream-share"), \
                 patch.object(setup, "CUSTOM", custom):
                setup.install()
                custom.write_bytes(custom.read_bytes().replace(b"</systemList>",
                                                             b"<!-- user edit --></systemList>"))
                with self.assertRaisesRegex(RuntimeError, "settings changed"):
                    setup.install()
                with self.assertRaisesRegex(RuntimeError, "settings changed"):
                    setup.restore_esde()


class RetroArchLauncherTest(unittest.TestCase):
    def test_unarmed_launcher_preserves_normal_retroarch_command(self):
        with tempfile.TemporaryDirectory() as root:
            home = Path(root) / "home"
            home.mkdir()
            fake = Path(root) / "retroarch"
            fake.write_text("#!/usr/bin/env python3\n"
                            "import os, sys\n"
                            "from pathlib import Path\n"
                            "Path(os.environ['TEST_OUTPUT']).write_text(repr(sys.argv[1:]))\n")
            fake.chmod(0o700)
            output = Path(root) / "output"
            env = os.environ.copy()
            env.update(HOME=str(home), TEST_OUTPUT=str(output))
            subprocess.run([sys.executable, str(ROOT / "retroarch/launch.py"),
                            str(fake), "-L", "mgba.so", "game.gba"],
                           env=env, check=True)
            self.assertEqual(output.read_text(), "['-L', 'mgba.so', 'game.gba']")

    def test_armed_launcher_uses_private_socket_and_session_config(self):
        with tempfile.TemporaryDirectory() as root:
            home = Path(root) / "home"
            runtime = Path(root) / "run"
            data = home / ".local/share/stream-share"
            data.mkdir(parents=True)
            runtime.mkdir()
            (data / "armed").touch()
            (data / "session.cfg").write_text('stdin_cmd_enable = "true"\n')
            fake = Path(root) / "retroarch"
            fake.write_text("#!/usr/bin/env python3\n"
                            "import os, sys\n"
                            "from pathlib import Path\n"
                            "Path(os.environ['TEST_OUTPUT']).write_text(repr(sys.argv[1:]) + '\\n' + sys.stdin.readline())\n")
            fake.chmod(0o700)
            output = Path(root) / "output"
            env = os.environ.copy()
            env.update(HOME=str(home), STREAM_SHARE_RUNTIME_DIR=str(runtime), TEST_OUTPUT=str(output))
            process = subprocess.Popen([sys.executable, str(ROOT / "retroarch/launch.py"),
                                        str(fake), "-L", "mgba.so", "game.gba"], env=env)
            control = runtime / "stream-share/retroarch.sock"
            try:
                for _ in range(100):
                    if control.is_socket():
                        break
                    time.sleep(0.02)
                self.assertTrue(control.is_socket())
                self.assertEqual(control.stat().st_mode & 0o777, 0o600)
                with patch.object(setup, "CONTROL", control):
                    self.assertTrue(setup.active())
                    setup.set_layout("side")
                self.assertEqual(process.wait(timeout=5), 0)
                text = output.read_text()
                self.assertIn("--appendconfig", text)
                self.assertIn("session.cfg", text)
                self.assertIn("--set-shader=", text)
                self.assertIn("SET_SHADER", text)
                self.assertIn("side.slangp", text)
            finally:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=5)


if __name__ == "__main__":
    unittest.main()
