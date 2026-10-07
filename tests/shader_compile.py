"""Compile both stages of RetroArch's combined Slang shader with glslangValidator."""

import subprocess
import tempfile
from pathlib import Path


source = (Path(__file__).parents[1] / "retroarch/pane.slang").read_text()
common, rest = source.split("#pragma stage vertex", 1)
vertex, fragment = rest.split("#pragma stage fragment", 1)
with tempfile.TemporaryDirectory() as directory:
    for extension, body, stage in (("vert", vertex, "vert"), ("frag", fragment, "frag")):
        path = Path(directory) / f"pane.{extension}"
        path.write_text(common + body)
        subprocess.run(["glslangValidator", "-V", "-S", stage, str(path),
                        "-o", str(path) + ".spv"], check=True)
