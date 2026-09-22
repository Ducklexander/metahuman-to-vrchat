# Stage 01 - import head.dna (and the body.dna next to it) through the Poly Hammer
# "Character DNA" addon.
#
# Facts this stage relies on (verified 2026-08-07 with Blender 5.1.0 and Character DNA 0.12.4):
#   * Operator: bpy.ops.character_dna.import_dna(...)
#   * `include_body=True` makes the importer also pick up `body.dna` sitting next to `head.dna`,
#     so head and body share one rig instance and are already aligned. No neck stitching needed.
#   * `import_shape_keys=True` is passed for completeness, but in the free edition the option is
#     read nowhere and imports nothing. Stage 02 reads the RigLogic corrective targets straight
#     out of the DNA instead.

import bpy

from .. import config


def clear_scene():
    """Wipe the startup scene so the import lands in a clean file."""
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for coll in (bpy.data.meshes, bpy.data.armatures, bpy.data.materials, bpy.data.images):
        for block in list(coll):
            if block.users == 0:
                coll.remove(block)


def main():
    cfg = config.get()
    # The importer refuses to run unless the scene unit scale is exactly 1.0.
    bpy.context.scene.unit_settings.scale_length = 1.0

    clear_scene()

    result = bpy.ops.character_dna.import_dna(
        filepath=str(cfg.head_dna),
        import_lod0=True,          # VRChat only needs LOD0; skip LOD1-7 entirely.
        import_lod1=False, import_lod2=False, import_lod3=False, import_lod4=False,
        import_lod5=False, import_lod6=False, import_lod7=False,
        import_mesh=True,
        # MUST stay False. The addon's DNAImporter.set_mesh_vertex_normals() feeds the DNA normals
        # through the same `* linear_modifier` path as the positions and never applies the Y-up ->
        # Z-up swizzle, so the imported custom split normals point in scrambled directions and the
        # head renders as speckled noise. The DNA marks no sharp edges, so Blender's own smooth
        # shading reproduces the intent exactly.
        import_normals=False,
        import_bones=True,
        import_shape_keys=True,    # no-op in 0.12.4; stage 02 does the real work
        import_vertex_groups=True,
        import_bone_collections=True,
        import_region_vertex_groups=False,
        import_vertex_colors=True,
        import_materials=True,
        import_face_board=True,    # the GUI rig; needed for the pose-library conversion in stage 03
        reuse_face_board=False,
        include_body=True,         # picks up body.dna next to head.dna
        alternate_maps_folder=str(cfg.face_textures_dir) if cfg.face_textures_dir else "",
    )
    assert result == {"FINISHED"}, f"import_dna returned {result}"
    return {"import_dna": sorted(result), "objects": len(bpy.data.objects)}
