# Stage 06 - strip everything that existed only to produce the bake.
#
# Run AFTER stage 04 and after the RigLogic checkpoint has been saved: this is destructive and
# leaves the file unable to re-evaluate RigLogic (the face board and the corrective blocks are
# what RigLogic writes into). checkpoint_riglogic.blend is the restore point.
#
# Removed here:
#   * the face board armature and its ~400 GUI meshes / empties  - authoring UI, not geometry
#   * all 782 RigLogic corrective shape keys                     - already folded into the bakes
#
# The corrective removal is the big one: 782 blocks x 24k verts is ~215 MB that would otherwise
# be written into the FBX and imported into Unity as 782 useless blendshapes.




import bpy

from .. import bake_expressions

GUI_PREFIXES = ("CTRL_", "TEXT_", "FRM_", "GRP_", "LOC_", "head_face_gui")


def remove_face_board():
    removed = 0
    for obj in list(bpy.data.objects):
        if obj.name.startswith(GUI_PREFIXES):
            bpy.data.objects.remove(obj, do_unlink=True)
            removed += 1
    return removed


def remove_correctives():
    """Delete every shape key that is not Basis and not one of our baked expressions."""
    keep = set(bake_expressions.build_bake_table()) | {"Basis"}
    stats = {}
    for obj in bpy.data.objects:
        if obj.type != "MESH" or not obj.data.shape_keys:
            continue
        doomed = [b for b in obj.data.shape_keys.key_blocks if b.name not in keep]
        for block in doomed:
            obj.shape_key_remove(block)
        stats[obj.name] = {
            "removed": len(doomed),
            "remaining": len(obj.data.shape_keys.key_blocks) if obj.data.shape_keys else 0,
        }
    return stats


def purge_orphans(passes=3):
    for _ in range(passes):
        bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)


def main():
    result = {"gui_objects_removed": remove_face_board()}
    result["shape_keys"] = remove_correctives()
    purge_orphans()
    result["objects_left"] = len(bpy.data.objects)
    return result


if __name__ == "__main__":
    main()
