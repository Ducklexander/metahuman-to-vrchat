# Stage 08 - fold the hair cards in and bring the body under the triangle budget.
#
# INPUTS
# ------
# The hair and eyebrow cards are separate FBX files you export from Unreal (see
# docs/02-unreal-export.md). Both are optional: a bald MetaHuman simply has no hair_fbx. Whatever
# the static meshes were called in UE, they are renamed here to HAIR_MESH / BROW_MESH so the later
# stages never depend on a particular groom (the original run used Hair_M_BobMessy and
# Eyebrows_M_Dense, both at LOD1).
#
# Use the LOD1 card meshes if you can. In my run LOD0 hair alone was 34,093 tris, which does not
# fit next to a 48k head that cannot be decimated; the artist-authored LOD1 was 18,738 tris and
# holds up at avatar viewing distance.
#
# EYEBROWS FOLLOW THE FACE
# ------------------------
# Bound rigidly to `head`, the eyebrow cards would sit frozen while browInnerUp / browDownLeft /
# noseSneer* move the skin underneath - very visible, and those are core ARKit shapes. So they are
# bound to the head mesh with a Surface Deform modifier and every expression is re-baked onto the
# cards: set the head's shape key to 1.0, let Surface Deform carry the cards along, and store the
# result as the card mesh's own shape key of the same name. After joining, one blendshape name
# drives both.
#
# The scalp hair gets no such treatment: it sits on the cranium, which no facial expression moves.
# It is bound rigidly to `head`.
#
# BODY DECIMATION
# ---------------
# The head component (~61.5k tris) cannot be decimated - Blender refuses to decimate a mesh with
# shape keys, and even if it did, collapsing edges would wreck the baked shapes. The body carries
# no shape keys, so it absorbs the whole reduction.

import bpy
import numpy as np

from .. import bake_expressions, config
from ..riglogic_core import activate  # shared operator-context helper

BODY_RIG = "head_body_rig"
HEAD_MESH = "head_head_lod0_mesh"
HAIR_MESH = "MH_HairCards"
BROW_MESH = "MH_BrowCards"
BODY_MESH = "head_body_lod0_mesh"

DELTA_THRESHOLD = 1e-5


def import_cards(path, target_name):
    """Import one card FBX and leave exactly one mesh object called `target_name`.

    The UE static-mesh export arrives at object scale 0.01 (centimetres) but already positioned on
    the skull in world space, so no manual alignment is needed - only a transform apply later.
    """
    if bpy.data.objects.get(target_name):
        return None
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=str(path), automatic_bone_orientation=True)
    new = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in new if o.type == "MESH"]
    assert meshes, f"{path.name} contained no mesh"

    for obj in meshes:
        world = obj.matrix_world.copy()
        obj.parent = None
        obj.matrix_world = world
    for obj in new:
        if obj.type != "MESH":
            bpy.data.objects.remove(obj, do_unlink=True)

    target = meshes[0]
    if len(meshes) > 1:
        view_layer = bpy.context.view_layer
        for obj in view_layer.objects:
            obj.select_set(False)
        for obj in meshes:
            obj.select_set(True)
        view_layer.objects.active = target
        with bpy.context.temp_override(object=target, active_object=target, selected_objects=meshes,
                                       selected_editable_objects=meshes, view_layer=view_layer):
            bpy.ops.object.join()
    source_name = target.name
    target.name = target_name
    target.data.name = target_name
    return {"from": path.name, "object": source_name, "joined": len(meshes)}


def evaluated_coords(obj):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    coords = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
    mesh.vertices.foreach_get("co", coords)
    evaluated.to_mesh_clear()
    return coords.reshape(-1, 3)


def apply_transforms(names):
    for name in names:
        obj = bpy.data.objects.get(name)
        if not obj:
            continue
        with activate(obj):
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)


def bind_to_head_bone(obj, rig):
    """Rigid skin: one vertex group `head` at weight 1, plus an armature modifier."""
    obj.parent = rig
    obj.matrix_parent_inverse = rig.matrix_world.inverted()
    group = obj.vertex_groups.get("head") or obj.vertex_groups.new(name="head")
    group.add(range(len(obj.data.vertices)), 1.0, "REPLACE")
    if not any(m.type == "ARMATURE" for m in obj.modifiers):
        modifier = obj.modifiers.new("Armature", "ARMATURE")
        modifier.object = rig


def bake_brows_from_head():
    """Surface-Deform the eyebrow cards to the head mesh and copy every expression onto them."""
    head = bpy.data.objects[HEAD_MESH]
    brows = bpy.data.objects[BROW_MESH]
    table = bake_expressions.build_bake_table()

    for block in head.data.shape_keys.key_blocks:
        block.value = 0.0
    bpy.context.view_layer.update()

    modifier = brows.modifiers.new("HeadSurfaceDeform", "SURFACE_DEFORM")
    modifier.target = head
    with activate(brows):
        bpy.ops.object.surfacedeform_bind(modifier=modifier.name)
    assert modifier.is_bound, "Surface Deform failed to bind the eyebrow cards to the head mesh"

    base = np.empty(len(brows.data.vertices) * 3, dtype=np.float32)
    brows.data.vertices.foreach_get("co", base)
    base = base.reshape(-1, 3)
    rest = evaluated_coords(brows)

    if brows.data.shape_keys is None:
        basis = brows.shape_key_add(name="Basis", from_mix=False)
        basis.id_data.name = brows.name

    baked = 0
    for shape_name in table:
        block = head.data.shape_keys.key_blocks.get(shape_name)
        if block is None:
            continue
        block.value = 1.0
        bpy.context.view_layer.update()
        delta = evaluated_coords(brows) - rest
        block.value = 0.0
        if float(np.abs(delta).max()) < DELTA_THRESHOLD:
            continue
        key = brows.shape_key_add(name=shape_name, from_mix=False)
        key.value = 0.0
        key.data.foreach_set("co", (base + delta).ravel())
        baked += 1

    bpy.context.view_layer.update()
    # The modifier has done its job; leaving it in would re-apply the deformation on top of the
    # baked keys (and Unity has no equivalent anyway).
    brows.modifiers.remove(modifier)
    return baked


def decimate_body(target_tris):
    body = bpy.data.objects[BODY_MESH]
    before = sum(len(p.vertices) - 2 for p in body.data.polygons)
    ratio = min(1.0, target_tris / before)

    modifier = body.modifiers.new("Decimate", "DECIMATE")
    modifier.decimate_type = "COLLAPSE"
    modifier.ratio = ratio
    modifier.use_collapse_triangulate = True

    with activate(body):
        bpy.ops.object.modifier_apply(modifier=modifier.name)
        after = sum(len(p.vertices) - 2 for p in body.data.polygons)
        # Decimation redistributes weights and can push a vertex past Unity's 4-influence cap.
        bpy.ops.object.vertex_group_limit_total(group_select_mode="ALL", limit=4)
        bpy.ops.object.vertex_group_normalize_all(group_select_mode="ALL", lock_active=False)
    return {"before": before, "ratio": round(ratio, 4), "after": after}


def main():
    cfg = config.get()
    rig = bpy.data.objects[BODY_RIG]
    result = {"imported": {}}
    if cfg.hair_fbx:
        result["imported"]["hair"] = import_cards(cfg.hair_fbx, HAIR_MESH)
    if cfg.eyebrow_fbx:
        result["imported"]["brows"] = import_cards(cfg.eyebrow_fbx, BROW_MESH)
    cards = [name for name in (HAIR_MESH, BROW_MESH) if bpy.data.objects.get(name)]
    apply_transforms(cards)

    result["brow_shapes_baked"] = bake_brows_from_head() if BROW_MESH in cards else 0

    for name in cards:
        bind_to_head_bone(bpy.data.objects[name], rig)

    result["body_decimate"] = decimate_body(cfg.body_tri_target)

    counts = {}
    for obj in bpy.data.objects:
        if obj.type == "MESH":
            counts[obj.name] = sum(len(p.vertices) - 2 for p in obj.data.polygons)
    result["tris"] = counts
    result["total_tris"] = sum(counts.values())
    return result
