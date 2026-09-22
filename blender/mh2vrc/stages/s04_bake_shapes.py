# Stage 04 - bake every entry in bake_expressions.py into shape keys.
#
# For each expression: pose the rig from raw controls, read each mesh's fully evaluated vertex
# positions (RigLogic correctives + armature skinning), and store them as a shape key.
#
#     shape_key_co = base_co + (evaluated_posed - evaluated_rest)
#
# The subtraction is not cosmetic. Round-tripping the joint transforms through
# decompose -> Matrix.LocRotScale -> skinning leaves the neutral pose about 0.04 mm off the raw
# mesh on the head; differencing against the measured rest pose cancels that exactly, so a shape
# at value 0 is bit-identical to the basis.
#
# Meshes are dropped here rather than later so the bake never spends time on geometry that
# will not ship (and so the shape-key memory is not wasted):
#   saliva    - the wet film between lips; invisible once the mouth has a real shader
#   eyeshell  - eye-occlusion shell; needs its own transparent material slot for a subtle effect
#   cartilage - inner nostril cartilage, only visible from inside the nose
# Kept: head, teeth (the MetaHuman "teeth" mesh contains the tongue), both eyes, eyelashes,
# eyeEdge (tear line).

import json

import time


import bpy
import numpy as np

from .. import bake_expressions, config, riglogic_core



DROP_MESHES = ["head_saliva_lod0_mesh", "head_eyeshell_lod0_mesh", "head_cartilage_lod0_mesh"]
# The mesh that always receives a shape key even when the delta is zero, so that every name in
# the table exists on the exported avatar (vrc.v_sil is deliberately a zero-delta shape).
PRIMARY_MESH = "head_head_lod0_mesh"

# 0.01 mm - below this a mesh is not meaningfully involved in the expression and gets no key.
DELTA_THRESHOLD = 1e-5


def drop_unused_meshes():
    removed = []
    for name in DROP_MESHES:
        obj = bpy.data.objects.get(name)
        if obj:
            mesh = obj.data
            bpy.data.objects.remove(obj, do_unlink=True)
            if mesh.users == 0:
                bpy.data.meshes.remove(mesh)
            removed.append(name)
    # Unconditional: on a re-run the meshes are already gone but the addon may still be holding
    # caches built while they existed (e.g. after an earlier failed attempt).
    riglogic_core.invalidate_caches()
    return removed


def ensure_basis(objects):
    """Guarantee a Basis key on every mesh we are about to bake onto.

    Blender treats the FIRST key block as the reference shape. The eyelash and tear-line meshes
    carry no RigLogic correctives, so they have no key blocks at all - adding an expression to
    them directly would silently make that expression the basis.
    """
    created = []
    for obj in objects:
        if obj.data.shape_keys is None:
            block = obj.shape_key_add(name="Basis", from_mix=False)
            block.id_data.name = obj.name
            created.append(obj.name)
    return created


def clear_previous_bake(objects, names):
    """Remove shape keys from an earlier run so this script is safe to re-run."""
    cleared = 0
    for obj in objects:
        keys = obj.data.shape_keys
        if not keys:
            continue
        for name in names:
            block = keys.key_blocks.get(name)
            if block is not None:
                obj.shape_key_remove(block)
                cleared += 1
    return cleared


def main():
    removed = drop_unused_meshes()

    driver = riglogic_core.RigDriver()
    table = bake_expressions.build_bake_table()
    cleared = clear_previous_bake([obj for _, _, obj in driver.head_meshes], list(table))

    started = time.time()
    result = {"removed_meshes": removed, "cleared_previous_keys": cleared, "shapes": {}, "per_mesh_counts": {}}

    result["basis_created"] = ensure_basis([obj for _, _, obj in driver.head_meshes])

    with driver:
        driver.reset()
        meshes = [(obj, obj.data) for _, _, obj in driver.head_meshes]

        base_coords, rest_coords = {}, {}
        for obj, mesh in meshes:
            base = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
            mesh.vertices.foreach_get("co", base)
            base_coords[obj.name] = base.reshape(-1, 3)
            rest_coords[obj.name] = driver.evaluated_coords(obj)

        for shape_name, controls in table.items():
            # Conditional correctives are baked against a driven base instead of the rest pose;
            # see bake_expressions.DIFFERENTIAL_BASE for why.
            base_controls = bake_expressions.DIFFERENTIAL_BASE.get(shape_name)
            reference = rest_coords
            if base_controls:
                driver.pose(base_controls)
                reference = {obj.name: driver.evaluated_coords(obj) for obj, _ in meshes}

            driver.pose(controls)
            entry = {"controls": controls, "differential_base": base_controls, "meshes": {}}

            for obj, _mesh in meshes:
                delta = driver.evaluated_coords(obj) - reference[obj.name]
                max_delta = float(np.abs(delta).max()) if delta.size else 0.0
                if max_delta < DELTA_THRESHOLD and obj.name != PRIMARY_MESH:
                    continue

                block = obj.shape_key_add(name=shape_name, from_mix=False)
                block.value = 0.0
                block.data.foreach_set("co", (base_coords[obj.name] + delta).ravel())
                entry["meshes"][obj.name] = round(max_delta * 1000, 3)  # mm
                result["per_mesh_counts"][obj.name] = result["per_mesh_counts"].get(obj.name, 0) + 1

            result["shapes"][shape_name] = entry

        driver.reset()

    result["shape_count"] = len(table)
    result["seconds"] = round(time.time() - started, 1)
    result["groups"] = bake_expressions.GROUPS
    result["unsupported_unified"] = bake_expressions.UNSUPPORTED_UNIFIED
    config.get().bake_result.write_text(json.dumps(result, indent=1), encoding="utf-8")

    return result


if __name__ == "__main__":
    main()
