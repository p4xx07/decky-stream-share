"""Install an isolated ES-DE GBA launch command and session-only shader files."""

import hashlib
import os
import shutil
import socket
import xml.etree.ElementTree as ET
from pathlib import Path


DATA = Path.home() / ".local" / "share" / "stream-share"
CUSTOM = Path.home() / "ES-DE" / "custom_systems" / "es_systems.xml"
CONTROL = Path(os.environ.get("STREAM_SHARE_RUNTIME_DIR", f"/run/user/{os.getuid()}")) / "stream-share" / "retroarch.sock"
LABEL = "mGBA"
GBA_EXTENSIONS = ".agb .AGB .bin .BIN .cgb .CGB .dmg .DMG .gb .GB .gba .GBA .gbc .GBC .sgb .SGB .7z .7Z .zip .ZIP"
PRESETS = {"side": (0.5, 1.0), "wide": (2 / 3, 1.0),
           "stack": (1.0, 0.5), "full": (1.0, 1.0)}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_atomic(path: Path, data: bytes) -> None:
    temp = path.with_name(path.name + ".stream-share-tmp")
    temp.write_bytes(data)
    temp.replace(path)


def install() -> str:
    if not CUSTOM.parent.parent.is_dir():
        raise RuntimeError("ES-DE was not found in your home folder. Install EmuDeck/ES-DE first.")
    DATA.mkdir(mode=0o700, parents=True, exist_ok=True)
    DATA.chmod(0o700)
    source = Path(__file__).resolve().parent
    shutil.copyfile(source / "pane.slang", DATA / "pane.slang")
    shutil.copyfile(source / "launch.py", DATA / "launch-gba")
    (DATA / "launch-gba").chmod(0o700)
    for layout, (width, height) in PRESETS.items():
        preset = (f'shaders = "1"\nshader0 = "pane.slang"\n'
                  f'scale_type0 = "viewport"\nfilter_linear0 = "false"\n'
                  f'parameters = "LocalWidth;LocalHeight"\n'
                  f'LocalWidth = "{width:.6f}"\nLocalHeight = "{height:.6f}"\n')
        (DATA / f"{layout}.slangp").write_text(preset, encoding="utf-8")
    config = (f'video_shader = "{DATA / "full.slangp"}"\n'
              'video_driver = "vulkan"\n'
              'video_shader_enable = "true"\n'
              'video_force_aspect = "false"\n'
              'video_scale_integer = "false"\n'
              'stdin_cmd_enable = "true"\n'
              'network_cmd_enable = "false"\n'
              'config_save_on_exit = "false"\n')
    (DATA / "session.cfg").write_text(config, encoding="utf-8")

    CUSTOM.parent.mkdir(parents=True, exist_ok=True)
    if CUSTOM.exists():
        original = CUSTOM.read_bytes()
        marker = DATA / "es_systems.installed.sha256"
        if marker.exists() and _sha(original) != marker.read_text(encoding="ascii"):
            raise RuntimeError("ES-DE settings changed after Stream Share setup. Restore the backup or remove the Stream Share GBA entry manually before refreshing.")
        parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True, insert_pis=True))
        root = ET.fromstring(original, parser=parser)
        if root.tag != "systemList":
            raise RuntimeError("ES-DE custom systems file has an unexpected root element")
    else:
        original = b""
        root = ET.Element("systemList")
    system = next((item for item in root.findall("system")
                   if item.findtext("name") == "gba"), None)
    if system is None:
        system = ET.SubElement(root, "system")
        for tag, value in (("name", "gba"), ("fullname", "Nintendo Game Boy Advance"),
                           ("path", "%ROMPATH%/gba"), ("extension", GBA_EXTENSIONS)):
            ET.SubElement(system, tag).text = value
        ET.SubElement(system, "platform").text = "gba"
        ET.SubElement(system, "theme").text = "gba"
    command = next((item for item in system.findall("command")
                    if item.get("label") == LABEL), None)
    if command is None:
        command = ET.Element("command", {"label": LABEL})
        anchor = next((index for index, item in enumerate(system) if item.tag == "command"),
                      len(system))
        system.insert(anchor, command)
    command.text = (f'{DATA / "launch-gba"} %EMULATOR_RETROARCH% '
                    '-L %CORE_RETROARCH%/mgba_libretro.so %ROM%')
    ET.indent(root, space="    ")
    updated = ET.tostring(root, encoding="utf-8", xml_declaration=True) + b"\n"
    if original != updated:
        backup = DATA / "es_systems.before-stream-share.xml"
        if not (DATA / "es_systems.installed.sha256").exists():
            _write_atomic(backup, original)
        _write_atomic(CUSTOM, updated)
        (DATA / "es_systems.installed.sha256").write_text(_sha(updated), encoding="ascii")
    (DATA / "armed").touch()
    return "GBA launcher ready. Restart ES-DE, then launch Pokémon from GBA."


def disarm() -> str:
    (DATA / "armed").unlink(missing_ok=True)
    return "GBA sharing disabled for future launches."


def restore_esde() -> str:
    marker = DATA / "es_systems.installed.sha256"
    backup = DATA / "es_systems.before-stream-share.xml"
    if not marker.exists() or not backup.exists():
        raise RuntimeError("No Stream Share ES-DE backup was found")
    if not CUSTOM.exists() or _sha(CUSTOM.read_bytes()) != marker.read_text(encoding="ascii"):
        raise RuntimeError("ES-DE settings changed after setup. Restore manually from the backup in ~/.local/share/stream-share.")
    original = backup.read_bytes()
    if original:
        _write_atomic(CUSTOM, original)
    else:
        CUSTOM.unlink()
    marker.unlink()
    disarm()
    return "Original ES-DE GBA configuration restored. Restart ES-DE."


def active() -> bool:
    try:
        with socket.socket(socket.AF_UNIX) as client:
            client.settimeout(0.2)
            client.connect(str(CONTROL))
            client.sendall(b"STATUS\n")
            return client.recv(16) == b"OK\n"
    except OSError:
        return False


def set_layout(layout: str) -> None:
    if layout not in PRESETS:
        raise ValueError("Unknown RetroArch layout")
    try:
        with socket.socket(socket.AF_UNIX) as client:
            client.settimeout(2)
            client.connect(str(CONTROL))
            client.sendall((layout + "\n").encode("ascii"))
            reply = client.recv(128)
    except OSError as exc:
        raise RuntimeError("No Stream Share GBA game is running. Prepare GBA, restart ES-DE, and launch the game first.") from exc
    if reply != b"OK\n":
        raise RuntimeError(reply.decode("ascii", errors="replace").strip() or "RetroArch did not answer")
