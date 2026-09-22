# Stage 02 - Import the RigLogic corrective (PSD) blend-shape targets from the DNA.
#
# WHY THIS SCRIPT EXISTS
# ----------------------
# The free edition of the Poly Hammer "Character DNA" addon 0.12.4 exposes an
# `import_shape_keys` import option, but *nothing in the addon ever reads it* - it is declared
# in properties.py and referenced nowhere else. The only shape-key reader in the codebase,
# `DNAImporter.get_dna_shape_keys()`, is dead code and is also broken (it does
# `mapping = []` then `mapping[vertex_index]`, and reads DeltaYs for the Z axis). Shape-key
# import is a Pro-edition feature ("Shape Key Editor" is listed in constants.PRO_EDITORS).
#
# Consequence if we skipped this: RigLogic would still drive the ~870 joints, but its
# blend-shape output layer (782 channels / 858 mesh targets) would land on nothing, so every
# baked expression would be missing all corrective/PSD deformation - lip roll, eyelid crease,
# cheek compression, etc. That is exactly the fidelity we came to Blender for.
#
# So we read the targets straight out of the DNA with the addon's own bundled `dna` bindings
# and author the shape keys ourselves, using the addon's naming convention so its own
# evaluation path (`RigInstance.head_shape_key_apply_plan`) picks them up automatically.
#
# NAMING
# ------
# The addon resolves driven blocks by the exact string f"{dna_mesh_name}__{channel_name}"
# (rig_instance.py: head_shape_key_blocks / head_shape_key_apply_plan). Blender's ID name
# limit is 63 chars, and 42 of the 858 targets are longer than that (deep combination
# correctives such as
# "head_lod0_mesh__Mfunnel_MupperLipRaise_MlowerLipDepress__funnelWide_UL" = 69 chars).
# Those 42 get a shortened `SHORT_MESH_PREFIX` name instead and are therefore invisible to
# the addon's plan - the bake script drives them manually from
# `head_instance.getBlendShapeOutputs()`. The mapping is written to a JSON sidecar so the
# bake script does not have to re-derive it.
#
# COORDINATE SPACE
# ----------------
# Verified empirically against the imported mesh (head_lod0_mesh vert 0 and 100):
#     blender_co = (dna_x, -dna_z, dna_y) * 0.01
# i.e. MetaHuman's Y-up centimetres -> Blender's Z-up metres. Deltas live in the same space,
# so the same swizzle+scale applies to them.

import json
import importlib


import bpy
import numpy as np

from .. import config

SHAPE_KEY_NAME_MAX_LENGTH = 63  # matches the addon's constants.SHAPE_KEY_NAME_MAX_LENGTH
LINEAR_MODIFIER = 0.01

# Short stand-in prefixes for the DNA mesh names, used only when the canonical
# "{mesh}__{channel}" name would blow past Blender's 63-char ID limit.
SHORT_MESH_PREFIX = {
    "head_lod0_mesh": "h0",
    "teeth_lod0_mesh": "te",
    "saliva_lod0_mesh": "sa",
    "eyeLeft_lod0_mesh": "el",
    "eyeRight_lod0_mesh": "er",
    "eyeshell_lod0_mesh": "es",
    "eyelashes_lod0_mesh": "la",
    "eyeEdge_lod0_mesh": "ee",
    "cartilage_lod0_mesh": "ca",
}


def get_instance():
    callbacks = importlib.import_module("bl_ext.api_portal_polyhammer_com.character_dna.ui.callbacks")
    instance = callbacks.get_active_rig_instance()
    assert instance is not None, "No active Character DNA rig instance - run stage 01 first."
    return instance


def dna_to_blender(dx, dy, dz):
    """Vectorised (x, y, z)_dna -> (x, -z, y)_blender * LINEAR_MODIFIER."""
    return np.stack([dx, -dz, dy], axis=1) * LINEAR_MODIFIER


def main():
    instance = get_instance()
    reader = instance.head_dna_reader
    mesh_lookup = instance.head_mesh_index_lookup

    manifest = {"canonical": {}, "shortened": {}, "meshes": {}}
    created = 0
    skipped_empty = 0

    for mesh_index in reader.getMeshIndicesForLOD(0):
        dna_mesh_name = reader.getMeshName(mesh_index)
        mesh_object = mesh_lookup.get(mesh_index)
        target_count = reader.getBlendShapeTargetCount(mesh_index)
        if not mesh_object or target_count == 0:
            continue

        mesh = mesh_object.data
        vertex_count = len(mesh.vertices)

        # Base (rest) positions, reused as the starting point for every target.
        base = np.empty(vertex_count * 3, dtype=np.float32)
        mesh.vertices.foreach_get("co", base)
        base = base.reshape(vertex_count, 3)

        # Basis block. The addon names the Key datablock after the mesh object, so mirror that.
        mesh_object.shape_key_clear()
        basis = mesh_object.shape_key_add(name="Basis", from_mix=False)
        basis.id_data.name = mesh_object.name

        mesh_entry = {"object": mesh_object.name, "dna_name": dna_mesh_name, "keys": {}}

        for target_index in range(target_count):
            channel_index = reader.getBlendShapeChannelIndex(mesh_index, target_index)
            channel_name = reader.getBlendShapeChannelName(channel_index)

            canonical = f"{dna_mesh_name}__{channel_name}"
            if len(canonical) <= SHAPE_KEY_NAME_MAX_LENGTH:
                block_name, is_canonical = canonical, True
            else:
                # Swapping the long DNA mesh name for a 2-char tag is not always enough (the
                # worst offender is still 64 chars), so embed the channel index - that keeps
                # the name unique even when the tail has to be truncated.
                block_name = f"{SHORT_MESH_PREFIX[dna_mesh_name]}{channel_index}__{channel_name}"[
                    :SHAPE_KEY_NAME_MAX_LENGTH
                ]
                is_canonical = False

            vertex_indices = np.asarray(reader.getBlendShapeTargetVertexIndices(mesh_index, target_index),
                                        dtype=np.int64)
            if vertex_indices.size == 0:
                skipped_empty += 1
                continue

            deltas = dna_to_blender(
                np.asarray(reader.getBlendShapeTargetDeltaXs(mesh_index, target_index), dtype=np.float32),
                np.asarray(reader.getBlendShapeTargetDeltaYs(mesh_index, target_index), dtype=np.float32),
                np.asarray(reader.getBlendShapeTargetDeltaZs(mesh_index, target_index), dtype=np.float32),
            )

            coords = base.copy()
            # A DNA vertex index can appear once per target; += keeps us safe if that ever changes.
            np.add.at(coords, vertex_indices, deltas)

            block = mesh_object.shape_key_add(name=block_name, from_mix=False)
            block.data.foreach_set("co", coords.ravel())
            # Blender may uniquify the name if something collided; record what we actually got.
            mesh_entry["keys"][str(channel_index)] = block.name
            (manifest["canonical"] if is_canonical else manifest["shortened"])[str(channel_index)] = [
                mesh_object.name,
                block.name,
            ]
            created += 1

        mesh.update()
        manifest["meshes"][str(mesh_index)] = mesh_entry

    config.get().correctives_sidecar.write_text(json.dumps(manifest, indent=1), encoding="utf-8")

    summary = {
        "created": created,
        "skipped_empty_targets": skipped_empty,
        "canonical_named": len(manifest["canonical"]),
        "shortened_named": len(manifest["shortened"]),
        "sidecar": str(config.get().correctives_sidecar),
    }

    return summary


if __name__ == "__main__":
    main()
