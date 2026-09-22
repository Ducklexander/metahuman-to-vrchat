# Stage 11 - independent verification of the exported FBX.
#
# Run in a SEPARATE Blender process started with --factory-startup (blender/run.py --verify does
# this), so nothing from the authoring session can mask a problem. Everything reported here is
# read back out of the FBX itself.

import json

import bpy
import numpy as np

from .. import bake_expressions, config


def main():
    cfg = config.get()
    FBX, OUT = cfg.fbx_out, cfg.verification
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(FBX), automatic_bone_orientation=False)

    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    armatures = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    assert len(meshes) == 1, f"expected one mesh, got {[m.name for m in meshes]}"
    assert len(armatures) == 1, f"expected one armature, got {[a.name for a in armatures]}"

    mesh_obj, rig = meshes[0], armatures[0]
    mesh = mesh_obj.data

    coords = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
    mesh.vertices.foreach_get("co", coords)
    coords = coords.reshape(-1, 3)
    world = np.array([mesh_obj.matrix_world @ v.co for v in mesh.vertices])

    key_names = [b.name for b in mesh.shape_keys.key_blocks] if mesh.shape_keys else []
    expected = bake_expressions.build_bake_table()

    bones = {b.name: (b.parent.name if b.parent else None) for b in rig.data.bones}

    influences = [sum(1 for g in v.groups if g.weight > 1e-6) for v in mesh.vertices]

    slot_tris = {}
    for polygon in mesh.polygons:
        slot = mesh_obj.material_slots[polygon.material_index]
        name = slot.material.name if slot.material else "<none>"
        slot_tris[name] = slot_tris.get(name, 0) + len(polygon.vertices) - 2

    report = {
        "fbx": str(FBX),
        "size_mb": round(FBX.stat().st_size / 1048576, 2),
        "objects": sorted(o.name for o in bpy.data.objects),
        "mesh_object": mesh_obj.name,
        "mesh_parent": mesh_obj.parent.name if mesh_obj.parent else None,
        "verts": len(mesh.vertices),
        "tris": sum(len(p.vertices) - 2 for p in mesh.polygons),
        "uv_layers": [layer.name for layer in mesh.uv_layers],
        "material_slots": [s.material.name if s.material else None for s in mesh_obj.material_slots],
        "tris_per_slot": slot_tris,
        "shape_key_count": len(key_names),
        "shape_key_names": key_names,
        "shape_keys_missing_vs_table": sorted(set(expected) - set(key_names)),
        "shape_keys_unexpected": sorted(set(key_names) - set(expected) - {"Basis"}),
        "shape_keys_with_zero_delta": [],
        "bone_count": len(bones),
        "bone_hierarchy": bones,
        "leaf_end_bones": [n for n in bones if n.endswith("_end")],
        "max_bone_influences": max(influences) if influences else 0,
        "verts_over_4_influences": sum(1 for i in influences if i > 4),
        "world_height_m": round(float(world[:, 2].max() - world[:, 2].min()), 4),
        "world_bbox_min": [round(float(v), 4) for v in world.min(0)],
        "world_bbox_max": [round(float(v), 4) for v in world.max(0)],
        "mesh_object_scale": [round(v, 6) for v in mesh_obj.matrix_world.to_scale()],
        "armature_scale": [round(v, 6) for v in rig.matrix_world.to_scale()],
    }

    if mesh.shape_keys:
        basis = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
        mesh.shape_keys.key_blocks[0].data.foreach_get("co", basis)
        for block in mesh.shape_keys.key_blocks[1:]:
            buffer = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
            block.data.foreach_get("co", buffer)
            if float(np.abs(buffer - basis).max()) < 1e-6:
                report["shape_keys_with_zero_delta"].append(block.name)

    groups = bake_expressions.GROUPS
    report["group_presence"] = {
        group: {"expected": len(names), "present": sum(1 for n in names if n in key_names)}
        for group, names in groups.items()
    }

    OUT.write_text(json.dumps(report, indent=1), encoding="utf-8")
    return {k: v for k, v in report.items() if k not in ("shape_key_names", "bone_hierarchy")}


if __name__ == "__main__":
    main()
