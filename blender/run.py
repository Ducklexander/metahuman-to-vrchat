# MetaHuman DNA -> VRChat-ready FBX, headless.
#
#   <blender.exe> -b --python blender/run.py -- --config my_config.toml
#
# Options (after the `--`):
#   --config PATH        required; see blender/config.example.toml
#   --from import|bake   import (default): full run from head.dna.
#                        bake: reload <work_dir>/checkpoint_riglogic.blend and redo everything
#                        after it. Use this after editing bake_expressions.py.
#   --qa                 also render contact sheets of the baked shapes into <work_dir>/qa/
#   --no-verify          skip the independent re-import check at the end
#   --verify             internal: run only the verification stage (started by the main run in
#                        a second, --factory-startup Blender process)
#
# Blender must be started WITHOUT --factory-startup for the main run: the Poly Hammer addon is a
# user extension and factory startup disables it.

import argparse
import importlib
import json
import subprocess
import sys
import time
from pathlib import Path

import bpy

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from mh2vrc import config, report  # noqa: E402

IMPORT_STAGES = [
    "s01_import_dna",
    "s02_import_correctives",
    "s03_extract_addon_poses",
]
BAKE_STAGES = [
    "s04_bake_shapes",
    "s05_spotcheck_render",       # only with --qa
    "s06_cleanup_after_bake",     # destructive: RigLogic can no longer be evaluated after this
    "s07_rig_to_humanoid",
    "s08_hair_and_body",
    "s08b_hair_reuv",
    "s09_merge_and_materials",
    "s10_export_fbx",
]


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(prog="blender -b --python blender/run.py --")
    parser.add_argument("--config", required=True)
    parser.add_argument("--from", dest="start", choices=["import", "bake"], default="import")
    parser.add_argument("--qa", action="store_true")
    parser.add_argument("--no-verify", action="store_true")
    parser.add_argument("--verify", action="store_true")
    return parser.parse_args(argv)


def log(message):
    print(f"[mh2vrc] {message}", flush=True)


def check_addon():
    """Fail early and clearly if the Poly Hammer addon is missing; warn on untested versions."""
    import addon_utils

    found = [m for m in addon_utils.modules() if m.__name__ == config.ADDON_MODULE]
    if not found:
        raise SystemExit(
            "Poly Hammer 'Character DNA' extension not found. Install it into this Blender from "
            "Poly Hammer's extension repository (see docs/01-prerequisites.md), and do not start "
            "Blender with --factory-startup.")
    version = tuple(found[0].bl_info.get("version", ()))
    enabled = addon_utils.check(config.ADDON_MODULE)[1]
    if not enabled:
        addon_utils.enable(config.ADDON_MODULE, default_set=True)
    if version not in config.TESTED_ADDON_VERSIONS:
        log(f"WARNING: Character DNA {version} is untested; this pipeline was verified with "
            f"{sorted(config.TESTED_ADDON_VERSIONS)}. Check the verification report carefully.")
    return version


def run_stage(name):
    module = importlib.import_module(f"mh2vrc.stages.{name}")
    started = time.time()
    log(f"{name} ...")
    result = module.main()
    log(f"{name} done in {time.time() - started:.1f} s")
    return result


def save(path):
    bpy.ops.wm.save_as_mainfile(filepath=str(path), compress=False)
    log(f"saved {path}")


def verify_in_clean_process(cfg):
    """Re-import the FBX in a fresh --factory-startup Blender so the authoring session cannot hide
    a problem (missing skeleton, dropped shape keys, wrong scale)."""
    command = [bpy.app.binary_path, "-b", "--factory-startup", "--python", str(Path(__file__).resolve()),
               "--", "--config", str(cfg.config_path), "--verify"]
    log("verifying in a clean Blender process ...")
    completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if completed.returncode != 0 or not cfg.verification.is_file():
        sys.stderr.write(completed.stdout[-4000:] + completed.stderr[-4000:])
        raise SystemExit("verification failed")
    return json.loads(cfg.verification.read_text(encoding="utf-8"))


def main():
    args = parse_args()
    cfg = config.load(args.config)
    config.set_active(cfg)

    if args.verify:
        summary = run_stage("s11_verify_fbx")
        log(json.dumps(summary, indent=1))
        return

    started = time.time()
    results = {"addon_version": list(check_addon())}

    if args.start == "import":
        for name in IMPORT_STAGES:
            results[name] = run_stage(name)
        save(cfg.checkpoint_blend)
    else:
        if not cfg.checkpoint_blend.is_file():
            raise SystemExit(f"--from bake needs {cfg.checkpoint_blend}; run the full pipeline once first")
        bpy.ops.wm.open_mainfile(filepath=str(cfg.checkpoint_blend))
        config.set_active(cfg)
        check_addon()

    for name in BAKE_STAGES:
        if name == "s05_spotcheck_render" and not args.qa:
            continue
        results[name] = run_stage(name)
        if name == "s06_cleanup_after_bake":
            save(cfg.stripped_blend)
        elif name == "s09_merge_and_materials":
            save(cfg.merged_blend)

    results["seconds"] = round(time.time() - started, 1)
    (cfg.work_dir / "run_result.json").write_text(json.dumps(results, indent=1, default=str), encoding="utf-8")

    if not args.no_verify:
        verification = verify_in_clean_process(cfg)
        path = report.write(cfg, verification)
        log(f"report: {path}")
        log(report.one_line(verification))
    log(f"finished in {time.time() - started:.1f} s -> {cfg.fbx_out}")


if __name__ == "__main__":
    try:
        main()
    except SystemExit as exc:
        if exc.code not in (0, None):
            print(f"[mh2vrc] ERROR: {exc}", file=sys.stderr, flush=True)
            sys.exit(1)
        raise
    except Exception:
        import traceback

        traceback.print_exc()
        sys.exit(1)
