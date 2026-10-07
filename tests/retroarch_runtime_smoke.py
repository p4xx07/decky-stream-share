"""Optional Linux check: load and switch the Slang shader in real RetroArch."""

import os
import subprocess
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).parents[1]
with tempfile.TemporaryDirectory() as temporary:
    directory = Path(temporary)
    (directory / "pane.slang").write_bytes((ROOT / "retroarch/pane.slang").read_bytes())
    for name, width in (("full", 1.0), ("side", 0.5)):
        (directory / f"{name}.slangp").write_text(
            f'shaders = "1"\nshader0 = "pane.slang"\nscale_type0 = "viewport"\n'
            f'parameters = "LocalWidth;LocalHeight"\n'
            f'LocalWidth = "{width}"\nLocalHeight = "1.0"\n')
    (directory / "session.cfg").write_text(
        f'video_driver = "vulkan"\nvideo_shader = "{directory / "full.slangp"}"\n'
        'video_shader_enable = "true"\nstdin_cmd_enable = "true"\n'
        'network_cmd_enable = "false"\nmenu_driver = "rgui"\n'
        'audio_enable = "false"\nconfig_save_on_exit = "false"\n')
    rom = directory / "blank.gba"
    content = bytearray(1024 * 1024)
    content[:4] = b"\xfe\xff\xff\xea"
    content[0xc0:0xc4] = b"\xfe\xff\xff\xea"
    rom.write_bytes(content)
    env = os.environ.copy()
    env["XDG_CONFIG_HOME"] = str(directory / "config")
    env["XDG_CACHE_HOME"] = str(directory / "cache")
    process = subprocess.Popen(
        ["retroarch", "--appendconfig", str(directory / "session.cfg"),
         f"--set-shader={directory / 'full.slangp'}", "--verbose",
         "-L", "/usr/lib/libretro/mgba_libretro.so", str(rom)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        env=env, text=True,
    )
    try:
        time.sleep(3)
        if process.poll() is not None:
            raise RuntimeError(f"RetroArch exited early: {process.stdout.read()}")
        process.stdin.write(f"SET_SHADER {directory / 'side.slangp'}\n")
        process.stdin.flush()
        time.sleep(3)
    finally:
        process.terminate()
        output, _ = process.communicate(timeout=8)
    interesting = [line for line in output.splitlines()
                   if "shader" in line.lower() or "slang" in line.lower()
                   or "command" in line.lower() or "side.slangp" in line.lower()]
    print("\n".join(interesting[-35:]))
    if "Command interface support" in output:
        raise AssertionError("Unexpected version output")
    if "Command \"" in output and "failed" in output:
        raise AssertionError("RetroArch rejected the shader command")
    if ("side.slangp" not in output
            or output.lower().count("[slang]: compiling shader") < 2):
        raise AssertionError("RetroArch did not load full and side shaders")
    config_path = directory / "config/retroarch/retroarch.cfg"
    if config_path.exists() and "side.slangp" in config_path.read_text():
        raise AssertionError("Temporary shader was saved to the base RetroArch config")
