# Stage 10 - export the avatar FBX to the path in [output] fbx.
#
# Export settings and why each one matters for a VRChat avatar:
#
#   use_selection=True            only Body + Armature; the QA camera must not ship
#   object_types={ARMATURE,MESH}
#   add_leaf_bones=False          Blender otherwise appends a "_end" bone to every leaf. Unity
#                                 imports those as real bones, which breaks Humanoid auto-mapping
#                                 on the fingers and inflates the bone count.
#   bake_anim=False               there is no animation to carry; a baked take would just bloat
#   use_mesh_modifiers=False      the only modifier is the Armature one, which must stay live.
#                                 Applying modifiers is also how shape keys get silently dropped.
#   mesh_smooth_type='FACE'       exports smoothing per face. Custom split normals were cleared
#                                 in stage 01 (the addon imports them wrong), so the mesh is fully
#                                 smooth-shaded and this round-trips correctly.
#   apply_unit_scale=True,
#   global_scale=1.0,
#   apply_scale_options='FBX_SCALE_NONE'
#                                 What Unity actually receives (measured in Unity 2022.3.22f1): the
#                                 FBX header declares centimetres, the vertex data is in metres,
#                                 and the Armature/Body nodes carry Lcl Scaling = 100. Unity's
#                                 useFileScale (fileScale 0.01) cancels the node scale, so the
#                                 avatar lands at the right height ONLY if useFileScale stays on.
#                                 Side effect: Armature and Body have lossyScale 100 in Unity, so
#                                 PhysBone radii must be divided by 100. Changing this to
#                                 FBX_SCALE_ALL is the likely root fix but is untested end to end.
#   axis_forward='-Z', axis_up='Y'  Unity's convention.
#   colors_type='NONE'            MetaHuman vertex colours were stripped in stage 09.
#   use_tspace=False              Unity recalculates tangents on import.
#
# All object transforms are asserted to be identity first: a non-identity object transform on a
# skinned mesh is the classic source of "avatar is 100x too big / rotated 90 degrees" in Unity.

import bpy
from mathutils import Matrix

from .. import config

MESH_NAME = "Body"
ARMATURE_OBJECT = "Armature"


def main():
    OUT = config.get().fbx_out
    body = bpy.data.objects[MESH_NAME]
    rig = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    rig.name = ARMATURE_OBJECT
    rig.data.name = ARMATURE_OBJECT

    identity = Matrix.Identity(4)
    for obj in (body, rig):
        delta = max(abs(a - b) for r1, r2 in zip(obj.matrix_world, identity) for a, b in zip(r1, r2))
        assert delta < 1e-5, f"{obj.name} has a non-identity transform (max delta {delta})"

    # The DNA importer leaves the armature hidden in the view layer, and select_set() is a no-op
    # on a hidden object - which silently exports the mesh with no skeleton at all. Unhide first.
    for obj in (body, rig):
        obj.hide_set(False)
        obj.hide_viewport = False

    view_layer = bpy.context.view_layer
    for obj in view_layer.objects:
        obj.select_set(False)
    body.select_set(True)
    rig.select_set(True)
    view_layer.objects.active = rig
    assert body.select_get() and rig.select_get(), "mesh and armature must both be selected"

    OUT.parent.mkdir(parents=True, exist_ok=True)
    selection = [body, rig]
    with bpy.context.temp_override(
        object=rig, active_object=rig,
        selected_objects=selection, selected_editable_objects=selection, view_layer=view_layer,
    ):
        bpy.ops.export_scene.fbx(
            filepath=str(OUT),
            use_selection=True,
            object_types={"ARMATURE", "MESH"},
            use_mesh_modifiers=False,
            mesh_smooth_type="FACE",
            use_subsurf=False,
            use_tspace=False,
            colors_type="NONE",
            use_custom_props=False,
            add_leaf_bones=False,
            primary_bone_axis="Y",
            secondary_bone_axis="X",
            armature_nodetype="NULL",
            bake_anim=False,
            path_mode="COPY",
            embed_textures=False,
            apply_unit_scale=True,
            apply_scale_options="FBX_SCALE_NONE",
            global_scale=1.0,
            axis_forward="-Z",
            axis_up="Y",
        )

    summary = {
        "path": str(OUT),
        "size_mb": round(OUT.stat().st_size / 1048576, 2),
        "mesh": MESH_NAME,
        "verts": len(body.data.vertices),
        "tris": sum(len(p.vertices) - 2 for p in body.data.polygons),
        "shape_keys": len(body.data.shape_keys.key_blocks),
        "material_slots": [s.material.name for s in body.material_slots],
        "bones": len(rig.data.bones),
    }
    return summary


if __name__ == "__main__":
    main()
