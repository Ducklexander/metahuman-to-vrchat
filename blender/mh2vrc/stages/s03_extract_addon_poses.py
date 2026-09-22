# Stage 03 - Convert the addon's bundled face-board pose library into raw control values.
#
# The Character DNA addon ships a pose library authored by Poly Hammer against this exact rig:
#   resources/poses/face/scan_reference/  - FACS-style single-action reference poses (~50)
#   resources/poses/face/visemes/         - phoneme mouth shapes
#   resources/poses/face/emotions/        - 24 graded emotions + 15 pairwise combinations
#
# Each pose.json stores face-board (GUI) pose-bone locations. Our bake pipeline drives RAW
# controls, so we convert once, exactly, by pushing the GUI values through RigLogic's own
# mapGUIToRawControls() and reading the raw layer back out. That is the same code path the addon
# uses interactively, so the conversion is lossless rather than an approximation.
#
# Output: <work_dir>/addon_poses_raw.json
#   { "<category>/<name>": {"description": ..., "tags": [...], "raw": {"jawOpen": 1.0, ...}} }
# Only non-zero raw controls are stored.

import json

from pathlib import Path

import bpy

from .. import config, riglogic_core


def poses_root() -> Path:
    """The addon's bundled face pose library, located from the installed module itself so it
    works whichever extension repository the user installed the addon from."""
    import importlib

    module = importlib.import_module(config.ADDON_MODULE)
    return Path(module.__file__).parent / "resources" / "poses" / "face"

AXIS_INDEX = {"x": 0, "y": 1, "z": 2}
EPSILON = 1e-5


def convert(driver, pose_json: dict) -> dict:
    """face-board pose -> {raw_control_short_name: value} using RigLogic's GUI->raw mapping."""
    board = pose_json.get("face_board", {})

    # Push every GUI control the DNA knows about; anything absent from the pose stays at 0.
    for index, control_name, axis in driver.instance.head_gui_control_plan:
        entry = board.get(control_name)
        value = entry["location"][AXIS_INDEX[axis]] if entry else 0.0
        driver.rig_logic.setGUIControl(index, float(value))

    driver.manager.mapGUIToRawControls(driver.rig_logic)

    raw_values = driver.rig_logic.getRawControlValues()
    result = {}
    for index, full_name in enumerate(driver.raw_names):
        value = float(raw_values[index])
        if abs(value) <= EPSILON:
            continue
        # Drop the neck/head quaternion channels: those encode head rotation, which must stay at
        # rest for a VRChat bake (head movement is the avatar's bones' job, not a blendshape's).
        if not full_name.startswith("CTRL_expressions."):
            continue
        result[full_name.split(".", 1)[1]] = round(value, 5)
    return result


def main():
    POSES_ROOT = poses_root()
    assert POSES_ROOT.is_dir(), f"addon pose library not found at {POSES_ROOT}"
    driver = riglogic_core.RigDriver()
    out = {}
    with driver:
        for category_dir in sorted(POSES_ROOT.iterdir()):
            if not category_dir.is_dir():
                continue
            for pose_dir in sorted(category_dir.rglob("pose.json")):
                key = str(pose_dir.parent.relative_to(POSES_ROOT)).replace("\\", "/")
                data = json.loads(pose_dir.read_text(encoding="utf-8"))
                out[key] = {
                    "description": data.get("description", ""),
                    "tags": data.get("tags", []),
                    "raw": convert(driver, data),
                }
        # convert() left the GUI layer dirty; the context manager's reset() only zeroes raw
        # controls, so clear the GUI side explicitly before handing the rig back.
        for index, _, _ in driver.instance.head_gui_control_plan:
            driver.rig_logic.setGUIControl(index, 0.0)
        driver.manager.mapGUIToRawControls(driver.rig_logic)

    out_path = config.get().addon_poses
    out_path.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    summary = {
        "poses": len(out),
        "by_category": {},
        "out": str(out_path),
    }
    for key in out:
        cat = key.split("/")[0]
        summary["by_category"][cat] = summary["by_category"].get(cat, 0) + 1

    return summary


if __name__ == "__main__":
    main()
