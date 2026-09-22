"""One command from your MetaHuman export to the files Unity needs.

    python build.py my_metahuman/config.toml

Runs the Blender bake (headless) and then the texture scripts, and leaves everything in the
config's work folder:

    work/Avatar.fbx       the avatar
    work/Textures/        18 PNG files
    work/bake_report.md   what was checked

Options:
    --blender PATH   blender.exe, if it is not set in the config ([blender] exe)
    --only blender   run only the bake        --only textures   run only the textures
    --from-bake      reuse the saved RigLogic checkpoint (after editing bake_expressions.py)
    --qa             also render contact sheets of the baked shapes into work/qa/
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

REPO = Path(__file__).resolve().parent
TEXTURES = REPO / "tools" / "textures"


def resolve(base: Path, value):
    if not value:
        return None
    path = Path(value).expanduser()
    return path if path.is_absolute() else (base / path).resolve()


def run(command, label):
    print(f"\n=== {label}", flush=True)
    started = time.time()
    result = subprocess.run([str(c) for c in command])
    if result.returncode != 0:
        sys.exit(f"{label} failed (exit code {result.returncode})")
    print(f"=== {label}: done in {time.time() - started:.0f} s", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("config")
    parser.add_argument("--blender")
    parser.add_argument("--only", choices=["blender", "textures"])
    parser.add_argument("--from-bake", action="store_true")
    parser.add_argument("--qa", action="store_true")
    args = parser.parse_args()

    config_path = Path(args.config).resolve()
    cfg = tomllib.loads(config_path.read_text(encoding="utf-8"))
    base = config_path.parent
    inputs, output = cfg.get("input", {}), cfg.get("output", {})
    work = resolve(base, output.get("work_dir", "work"))
    textures_out = work / "Textures"

    if args.only != "textures":
        blender = args.blender or cfg.get("blender", {}).get("exe")
        if not blender or not Path(blender).is_file():
            sys.exit("Set the path to blender.exe with --blender or under [blender] exe in the config.")
        command = [blender, "-b", "--python", REPO / "blender" / "run.py", "--", "--config", config_path]
        if args.from_bake:
            command += ["--from", "bake"]
        if args.qa:
            command.append("--qa")
        run(command, "Blender bake")

    if args.only != "blender":
        src = resolve(base, inputs.get("textures_dir"))
        dcc = resolve(base, inputs.get("face_textures_dir"))
        if not src or not dcc:
            sys.exit("Set [input] textures_dir and face_textures_dir in the config to build textures.")
        py = sys.executable
        run([py, TEXTURES / "build_textures.py", "--src", src, "--dcc", dcc, "--out", textures_out], "Skin, eye and teeth textures")
        hair = [py, TEXTURES / "hair_atlas.py", "--out", textures_out]
        params = resolve(base, inputs.get("hair_params"))
        if params:
            hair += ["--params", params]
        run(hair, "Hair atlas")
        run([py, TEXTURES / "eyeedge_texture.py", "--out", textures_out], "Tear line texture")
        run([py, TEXTURES / "skin_detail_normal.py", "--out", textures_out], "Pore detail normal")

    print(f"\nDone. Copy into Unity: {work / 'Avatar.fbx'} and the folder {textures_out}")


if __name__ == "__main__":
    main()
