# Stage 07 - collapse two MetaHuman rigs (875 + 342 bones) into one Unity Humanoid
# skeleton, without changing the rest shape of any mesh.
#
# THE TWO RIGS
# ------------
# The DNA import produces `head_head_rig` (875 bones) and `head_body_rig` (342). They overlap:
# both carry root/pelvis/spine_01..05/neck_01/neck_02/head. Measured, the two agree to ~1e-5 from
# spine_04 upward but disagree by up to 18 mm at spine_01..03 and completely at `root` - the
# addon synthesises the head rig's lower spine from hardcoded proportions (constants.EXTRA_BONES)
# rather than from the DNA. So the BODY rig is the authority for the skeleton, and all we take
# from the head rig are the two eyeball joints.
#
# WEIGHT MERGING
# --------------
# Every bone we drop has its vertex weights added to its nearest surviving ancestor. Because a
# bone at rest contributes the identity transform, this leaves the rest pose bit-identical; only
# animation fidelity changes, and the fidelity we are dropping (785 facial joints, twist and
# corrective joints) is either already baked into blendshapes or has no driver in VRChat anyway.
#
# WHAT SURVIVES
# -------------
# Exactly the Unity Humanoid set. Spine is thinned 5 -> 3 (spine_01/03/05 = Spine/Chest/
# UpperChest) and neck 2 -> 1, because Unity's Humanoid mapper wants a contiguous mapped chain
# and unmapped intermediate bones make the avatar fail to configure.




import bpy


HEAD_RIG = "head_head_rig"
BODY_RIG = "head_body_rig"

# MetaHuman's eyeball joints. The eye meshes are 100% weighted to these (plus a Pupil scale joint
# that we merge in, since pupil dilation is now a blendshape).
EYE_SOURCE = {"FACIAL_L_EyeParallel": "eye_l", "FACIAL_R_EyeParallel": "eye_r"}

FINGERS = ["thumb", "index", "middle", "ring", "pinky"]

KEEP_BONES = (
    ["root", "pelvis", "spine_01", "spine_03", "spine_05", "neck_01", "head"]
    + list(EYE_SOURCE.values())
    + [f"{part}_{side}" for side in ("l", "r")
       for part in ("clavicle", "upperarm", "lowerarm", "hand", "thigh", "calf", "foot", "ball")]
    + [f"{finger}_0{i}_{side}" for side in ("l", "r") for finger in FINGERS for i in (1, 2, 3)]
)

HEAD_COMPONENT_MESHES = [
    "head_head_lod0_mesh",
    "head_teeth_lod0_mesh",
    "head_eyeLeft_lod0_mesh",
    "head_eyeRight_lod0_mesh",
    "head_eyelashes_lod0_mesh",
    "head_eyeEdge_lod0_mesh",
]

LEFTOVER_EMPTIES = ["eyesSetup_grp", "headGui_grp", "headRig_grp", "headRigging_grp", "head_grp", "sphere_control"]


from ..riglogic_core import activate  # shared operator-context helper


def ancestor_map(armature_obj, keep: set) -> dict:
    """{bone_name: nearest ancestor that survives} for every bone that does not."""
    mapping = {}
    for bone in armature_obj.data.bones:
        if bone.name in keep:
            continue
        parent = bone.parent
        while parent is not None and parent.name not in keep:
            parent = parent.parent
        mapping[bone.name] = parent.name if parent else None
    return mapping


def merge_weights(mesh_obj, mapping: dict, rename: dict | None = None):
    """Fold each doomed vertex group into its surviving ancestor's group, then delete it."""
    rename = rename or {}
    groups = mesh_obj.vertex_groups
    stats = {"merged": 0, "dropped_no_ancestor": 0, "renamed": 0}

    # Collect the weights first: adding to a group while iterating its own data is fine, but we
    # need the doomed group's weights before removing it.
    transfers = {}
    for group in list(groups):
        target = mapping.get(group.name, "__keep__")
        if target == "__keep__":
            continue
        if target is None:
            stats["dropped_no_ancestor"] += 1
            groups.remove(group)
            continue
        transfers.setdefault(target, []).append(group.index)

    if transfers:
        index_to_target = {}
        for target, indices in transfers.items():
            for index in indices:
                index_to_target[index] = target

        accumulated = {target: {} for target in transfers}
        for vertex in mesh_obj.data.vertices:
            for element in vertex.groups:
                target = index_to_target.get(element.group)
                if target is not None and element.weight > 0.0:
                    bucket = accumulated[target]
                    bucket[vertex.index] = bucket.get(vertex.index, 0.0) + element.weight

        for target, weights in accumulated.items():
            group = groups.get(target) or groups.new(name=target)
            for vertex_index, weight in weights.items():
                group.add([vertex_index], min(weight, 1.0), "ADD")
            stats["merged"] += 1

        for index in sorted(index_to_target, reverse=True):
            groups.remove(groups[index])

    for old, new in rename.items():
        group = groups.get(old)
        if group:
            group.name = new
            stats["renamed"] += 1
    return stats


def copy_eye_bones():
    """Add the two eyeball joints to the body rig, at their head-rig rest transforms."""
    head_rig = bpy.data.objects[HEAD_RIG]
    body_rig = bpy.data.objects[BODY_RIG]
    world = {name: head_rig.matrix_world @ head_rig.data.bones[name].matrix_local for name in EYE_SOURCE}
    lengths = {name: head_rig.data.bones[name].length for name in EYE_SOURCE}

    added = []
    with activate(body_rig):
        bpy.ops.object.mode_set(mode="EDIT")
        for source, new_name in EYE_SOURCE.items():
            if new_name in body_rig.data.edit_bones:
                continue
            matrix = body_rig.matrix_world.inverted() @ world[source]
            bone = body_rig.data.edit_bones.new(new_name)
            bone.head = (0, 0, 0)
            bone.tail = (0, max(lengths[source], 0.01), 0)
            bone.matrix = matrix
            bone.parent = body_rig.data.edit_bones["head"]
            bone.use_connect = False
            added.append(new_name)
        bpy.ops.object.mode_set(mode="OBJECT")
    return added


def delete_bones(armature_obj, keep: set):
    with activate(armature_obj):
        bpy.ops.object.mode_set(mode="EDIT")
        edit_bones = armature_obj.data.edit_bones
        doomed = [b for b in edit_bones if b.name not in keep]
        # Re-parent survivors explicitly rather than trusting the operator's implicit fix-up.
        for bone in edit_bones:
            if bone.name in keep:
                parent = bone.parent
                while parent is not None and parent.name not in keep:
                    parent = parent.parent
                bone.parent = parent
                bone.use_connect = False
        for bone in doomed:
            edit_bones.remove(bone)
        bpy.ops.object.mode_set(mode="OBJECT")
    return len(doomed)


def retarget_to_body_rig():
    body_rig = bpy.data.objects[BODY_RIG]
    moved = []
    for name in HEAD_COMPONENT_MESHES:
        obj = bpy.data.objects.get(name)
        if not obj:
            continue
        world = obj.matrix_world.copy()
        obj.parent = body_rig
        obj.matrix_world = world
        for modifier in obj.modifiers:
            if modifier.type == "ARMATURE":
                modifier.object = body_rig
        moved.append(name)
    return moved


def limit_and_normalize(mesh_names, limit=4):
    """Unity's skinned mesh renderer caps at 4 bone influences per vertex; enforce it here."""
    stats = {}
    for name in mesh_names:
        obj = bpy.data.objects.get(name)
        if not obj:
            continue
        with activate(obj):
            bpy.ops.object.vertex_group_limit_total(group_select_mode="ALL", limit=limit)
            bpy.ops.object.vertex_group_normalize_all(group_select_mode="ALL", lock_active=False)
        stats[name] = max(
            (sum(1 for g in v.groups if g.weight > 1e-6) for v in obj.data.vertices), default=0
        )
    return stats


def main():
    # `bpy.context.object` is not even defined right after opening a file with nothing active.
    if getattr(bpy.context, "object", None) and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")

    result = {}
    head_rig = bpy.data.objects[HEAD_RIG]
    body_rig = bpy.data.objects[BODY_RIG]

    result["eye_bones_added"] = copy_eye_bones()

    keep = set(KEEP_BONES)

    # Head component: everything facial folds into `head`, except the two eyeball joints which
    # survive under their new names.
    head_keep = (keep - set(EYE_SOURCE.values())) | set(EYE_SOURCE)
    head_mapping = ancestor_map(head_rig, head_keep)
    result["head_merges"] = {}
    for name in HEAD_COMPONENT_MESHES:
        obj = bpy.data.objects.get(name)
        if obj:
            result["head_merges"][name] = merge_weights(obj, head_mapping, rename=EYE_SOURCE)

    result["retargeted"] = retarget_to_body_rig()

    # Body component: twists, bulges and correctives fold into the Humanoid chain.
    body_mapping = ancestor_map(body_rig, keep)
    body_mesh = bpy.data.objects["head_body_lod0_mesh"]
    result["body_merge"] = merge_weights(body_mesh, body_mapping)

    result["bones_deleted"] = delete_bones(body_rig, keep)
    result["bones_left"] = len(body_rig.data.bones)

    all_meshes = HEAD_COMPONENT_MESHES + ["head_body_lod0_mesh"]
    result["max_influences"] = limit_and_normalize(all_meshes)

    # The head rig and the leftover import scaffolding have no further use.
    for name in [HEAD_RIG, *LEFTOVER_EMPTIES]:
        obj = bpy.data.objects.get(name)
        if obj:
            bpy.data.objects.remove(obj, do_unlink=True)

    result["objects"] = sorted(o.name for o in bpy.data.objects)
    return result


if __name__ == "__main__":
    main()
