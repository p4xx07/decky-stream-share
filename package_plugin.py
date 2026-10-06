"""Package the Decky plugin and the separate PC relay."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parent
VERSION = "0.1.0-alpha.6"
OUTPUT = ROOT / f"StreamShare-{VERSION}.zip"
RELAY_OUTPUT = ROOT / f"StreamShareRelay-{VERSION}.zip"
FILES = ["plugin.json", "package.json", "main.py", "LICENSE", "README.md",
         "dist/index.js", "bin/stream-share-renderer"]
PY_MODULE_FILES = ["relay/__init__.py", "relay/client.py", "relay/audio.py"]
RELAY_FILES = ["relay/server.py", "relay/client.html", "relay/requirements.txt", "relay/README.md"]


if __name__ == "__main__":
    for name in FILES + PY_MODULE_FILES + RELAY_FILES:
        if not (ROOT / name).is_file():
            raise SystemExit(f"Missing {name}; build the frontend and helper first")
    with ZipFile(OUTPUT, "w", ZIP_DEFLATED) as archive:
        for name in FILES:
            archive.write(ROOT / name, f"Stream Share/{name}")
        for name in PY_MODULE_FILES:
            archive.write(ROOT / name, f"Stream Share/py_modules/{name}")
    print(OUTPUT)
    with ZipFile(RELAY_OUTPUT, "w", ZIP_DEFLATED) as archive:
        for name in RELAY_FILES:
            archive.write(ROOT / name, f"StreamShareRelay/{Path(name).name}")
        archive.write(OUTPUT, "StreamShareRelay/d.zip")
    print(RELAY_OUTPUT)
