# Stage 09 - merge every part into one skinned mesh with <= 8 material slots.
#
# The result is a single object named `Body`. That name is not cosmetic: Adjerry91's VRCFT
# Templates (and a lot of VRChat tooling) look for the blendshape-carrying skinned mesh under
# exactly that name.
#
# UV LAYERS
# ---------
# The DNA meshes carry `DiffuseUV`; the UE-exported hair cards carry `LightMapUV`. Blender's join
# takes the union of layer names, so mixing them would leave the hair with all-zero UVs in
# `DiffuseUV` and the face with all-zero UVs in `LightMapUV` - two half-empty channels. Every
# layer is therefore renamed to `UVMap` first so everything lands in UV0, which is what Poiyomi
# reads.
#
# MATERIAL SLOTS (7, under the VRChat "Good" rank ceiling of 8)
#   1 Skin_Head      head mesh
#   2 Skin_Body      body mesh
#   3 Eye_L          left eyeball
#   4 Eye_R          right eyeball
#   5 Teeth_Tongue   the MetaHuman "teeth" mesh, which contains the tongue
#   6 EyeEdge        tear line (alpha)
#   7 Hair           scalp cards, eyebrow cards AND eyelashes
#
# Hair, eyebrows and lashes deliberately share one slot. UE's hair shader is procedural, with no
# atlas to export, so a strand atlas has to be authored from scratch either way; all three are
# hair, all three are built as thin per-card UV strips, and putting them in one atlas costs nothing
# extra. That leaves an eighth slot free for clothing.

import bpy

from .s08_hair_and_body import BROW_MESH, HAIR_MESH

MERGED_NAME = "Body"
UV_NAME = "UVMap"

# object name -> target material slot name. Order here is the final slot order.
SLOT_ASSIGNMENT = [
    ("Skin_Head", ["head_head_lod0_mesh"]),
    ("Skin_Body", ["head_body_lod0_mesh"]),
    ("Eye_L", ["head_eyeLeft_lod0_mesh"]),
    ("Eye_R", ["head_eyeRight_lod0_mesh"]),
    ("Teeth_Tongue", ["head_teeth_lod0_mesh"]),
    ("EyeEdge", ["head_eyeEdge_lod0_mesh"]),
    ("Hair", [
        HAIR_MESH,
        BROW_MESH,
        "head_eyelashes_lod0_mesh",
    ]),
]

# MetaHuman lays the body out in the U 1..2 UDIM tile, not 0..1. Unity's default Repeat wrap makes
# that work by accident, but it breaks the moment anyone sets the texture to Clamp, and it makes
# the UVs confusing to inspect. Shifted back into 0..1 here since the body has its own material.
UDIM_SHIFT = {"head_body_lod0_mesh": (-1.0, 0.0)}

# Hair and eyebrow cards come from optional inputs; everything else must exist.
OPTIONAL = {HAIR_MESH, BROW_MESH}


def normalise_uvs(objects):
    renamed = {}
    for obj in objects:
        layers = obj.data.uv_layers
        if not layers:
            layers.new(name=UV_NAME)
        for index, layer in enumerate(list(layers)):
            if index == 0:
                renamed[obj.name] = layer.name
                layer.name = UV_NAME
            else:
                layers.remove(layer)
    return renamed


def shift_udim_tiles(objects):
    """Move any mesh authored in a non-zero UDIM tile back into the 0..1 square."""
    import numpy as np

    moved = {}
    for obj in objects:
        offset = UDIM_SHIFT.get(obj.name)
        if not offset:
            continue
        layer = obj.data.uv_layers[0]
        uvs = np.empty(len(obj.data.loops) * 2, dtype=np.float32)
        layer.uv.foreach_get("vector", uvs)
        uvs = uvs.reshape(-1, 2) + np.asarray(offset, dtype=np.float32)
        layer.uv.foreach_set("vector", uvs.ravel())
        moved[obj.name] = {"offset": list(offset),
                           "u": [round(float(uvs[:, 0].min()), 4), round(float(uvs[:, 0].max()), 4)]}
    return moved


def strip_colour_attributes(objects):
    """MetaHuman vertex colours encode masks for UE's skin shader; Poiyomi never reads them."""
    removed = []
    for obj in objects:
        # Read the names first: removing an attribute invalidates every other RNA pointer in the
        # collection, so iterating over live pointers blows up on the second removal.
        for name in [attribute.name for attribute in obj.data.color_attributes]:
            attribute = obj.data.color_attributes.get(name)
            if attribute is not None:
                obj.data.color_attributes.remove(attribute)
                removed.append(f"{obj.name}:{name}")
    return removed


def assign_single_material(obj, material_name):
    material = bpy.data.materials.get(material_name) or bpy.data.materials.new(material_name)
    obj.data.materials.clear()
    obj.data.materials.append(material)
    for polygon in obj.data.polygons:
        polygon.material_index = 0
    return material


def main():
    objects = []
    for slot_name, members in SLOT_ASSIGNMENT:
        for name in members:
            obj = bpy.data.objects.get(name)
            if obj is None and name in OPTIONAL:
                continue
            assert obj is not None, f"missing object {name}"
            assign_single_material(obj, slot_name)
            objects.append(obj)

    result = {"uv_renamed_from": normalise_uvs(objects)}
    result["udim_shifted"] = shift_udim_tiles(objects)
    result["colour_attributes_removed"] = strip_colour_attributes(objects)

    # Join into the head mesh: it holds all 169 expressions, so it makes the cleanest base.
    target = bpy.data.objects["head_head_lod0_mesh"]
    view_layer = bpy.context.view_layer
    for obj in view_layer.objects:
        obj.select_set(False)
    for obj in objects:
        obj.hide_set(False)
        obj.hide_viewport = False
        obj.select_set(True)
    view_layer.objects.active = target
    with bpy.context.temp_override(
        object=target, active_object=target,
        selected_objects=objects, selected_editable_objects=objects, view_layer=view_layer,
    ):
        bpy.ops.object.join()

    target.name = MERGED_NAME
    target.data.name = MERGED_NAME

    # Blender appends the joined objects' slots; rebuild the slot list in our intended order and
    # remap the polygons, so Unity sees a predictable ordering.
    existing = {slot.material.name: index for index, slot in enumerate(target.material_slots) if slot.material}
    order = [name for name, _ in SLOT_ASSIGNMENT if name in existing]
    remap = {existing[name]: new_index for new_index, name in enumerate(order)}
    polygon_indices = [remap[p.material_index] for p in target.data.polygons]

    target.data.materials.clear()
    for name in order:
        target.data.materials.append(bpy.data.materials[name])
    for polygon, index in zip(target.data.polygons, polygon_indices):
        polygon.material_index = index

    # One armature modifier, one parent.
    for modifier in list(target.modifiers):
        if modifier.type != "ARMATURE":
            target.modifiers.remove(modifier)
    armatures = [m for m in target.modifiers if m.type == "ARMATURE"]
    for extra in armatures[1:]:
        target.modifiers.remove(extra)

    keys = target.data.shape_keys
    result.update({
        "object": target.name,
        "verts": len(target.data.vertices),
        "tris": sum(len(p.vertices) - 2 for p in target.data.polygons),
        "material_slots": [s.material.name for s in target.material_slots],
        "shape_keys": len(keys.key_blocks) if keys else 0,
        "uv_layers": [layer.name for layer in target.data.uv_layers],
        "vertex_groups": len(target.vertex_groups),
        "modifiers": [(m.type, m.object.name if getattr(m, "object", None) else None) for m in target.modifiers],
    })
    return result


if __name__ == "__main__":
    main()
