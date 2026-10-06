"""Package the Decky probe after building its frontend and native helper."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "StreamShareProbe-0.0.3.zip"
FILES = ["plugin.json", "package.json", "main.py", "LICENSE", "README.md",
         "dist/index.js", "bin/stream-share-probe"]


if __name__ == "__main__":
    for name in FILES:
        if not (ROOT / name).is_file():
            raise SystemExit(f"Missing {name}; build the frontend and helper first")
    with ZipFile(OUTPUT, "w", ZIP_DEFLATED) as archive:
        for name in FILES:
            archive.write(ROOT / name, f"Stream Share Probe/{name}")
    print(OUTPUT)
