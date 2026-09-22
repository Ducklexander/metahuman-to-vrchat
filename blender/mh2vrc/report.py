# Writes <work_dir>/bake_report.md from the machine-readable results, so the numbers in the report
# are always the numbers that were produced.

import json
from datetime import date

from . import bake_expressions

# What a correct run looks like. The ARKit and viseme groups are hard requirements for the
# face-tracking template and the VRChat lip-sync; the triangle and slot figures are VRChat
# ranking thresholds rather than pass/fail rules.
CHECKS = [
    ("ARKit 52 present", lambda v: v["group_presence"]["ARKit52"]["present"] == 52),
    ("15 VRChat visemes present", lambda v: v["group_presence"]["Visemes"]["present"] == 15),
    ("single mesh named Body", lambda v: v["mesh_object"] == "Body"),
    ("no shape keys missing vs the bake table", lambda v: not v["shape_keys_missing_vs_table"]),
    ("max 4 bone influences per vertex", lambda v: v["max_bone_influences"] <= 4),
    ("no leaf _end bones", lambda v: not v["leaf_end_bones"]),
    ("material slots <= 8 (VRChat Good)", lambda v: len(v["material_slots"]) <= 8),
    ("only vrc.v_sil has zero delta", lambda v: set(v["shape_keys_with_zero_delta"]) <= {"vrc.v_sil"}),
]


def one_line(v):
    groups = v["group_presence"]
    return (f"{v['shape_key_count']} shape keys incl. Basis | ARKit {groups['ARKit52']['present']}/52 | "
            f"visemes {groups['Visemes']['present']}/15 | {v['tris']:,} tris | "
            f"{len(v['material_slots'])} material slots | {v['bone_count']} bones")


def _controls(controls):
    if not controls:
        return "_(neutral, zero delta)_"
    return "<br>".join(f"`{k}` = {value:g}" for k, value in sorted(controls.items()))


def write(cfg, verification):
    bake = json.loads(cfg.bake_result.read_text(encoding="utf-8")) if cfg.bake_result.is_file() else {}
    shapes = bake.get("shapes", {})
    lines = [
        "# Bake report",
        "",
        f"Generated {date.today().isoformat()} by blender/run.py. Everything below is read back from",
        f"`{cfg.fbx_out.name}` in a clean Blender process, not taken from the authoring session.",
        "",
        "## Summary",
        "",
        one_line(verification),
        "",
        "| Check | Result |",
        "| --- | --- |",
    ]
    for label, check in CHECKS:
        try:
            ok = bool(check(verification))
        except (KeyError, TypeError):
            ok = False
        lines.append(f"| {label} | {'pass' if ok else 'FAIL'} |")
    lines += [
        "",
        f"FBX size: {verification['size_mb']} MB. Height: {verification['world_height_m']} m.",
        f"Bake time: {bake.get('seconds', '?')} s for {bake.get('shape_count', '?')} shapes.",
        "",
        "Triangles per material slot:",
        "",
        "| Slot | Triangles |",
        "| --- | --- |",
    ]
    lines += [f"| {name} | {tris:,} |" for name, tris in verification["tris_per_slot"].items()]
    lines += ["", "## Mapping table", ""]
    for group, names in bake_expressions.GROUPS.items():
        lines += [f"### {group} ({len(names)})", "", "| Shape | Raw controls | Max delta (mm) |", "| --- | --- | --- |"]
        for name in names:
            entry = shapes.get(name)
            if entry is None:
                lines.append(f"| `{name}` | missing | - |")
                continue
            max_mm = max(entry["meshes"].values()) if entry["meshes"] else 0.0
            base = entry.get("differential_base")
            note = f"<br>_differential base:_ {_controls(base)}" if base else ""
            lines.append(f"| `{name}` | {_controls(entry['controls'])}{note} | {max_mm:g} |")
        lines.append("")
    if bake_expressions.UNSUPPORTED_UNIFIED:
        lines += ["## Unified Expressions the rig cannot produce", ""]
        lines += [f"- `{name}`: {why}" for name, why in bake_expressions.UNSUPPORTED_UNIFIED.items()]
    path = cfg.work_dir / "bake_report.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
