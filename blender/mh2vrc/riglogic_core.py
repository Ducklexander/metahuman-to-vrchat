# Shared RigLogic driving helpers.
#
# Everything downstream (verification, baking, spot-checks) goes through this module so there is
# exactly one definition of "pose the rig at these control values and read the result".
#
# WHY WE DRIVE *RAW* CONTROLS, NOT THE FACE BOARD
# ----------------------------------------------
# RigLogic's pipeline is:  GUI controls -> mapGUIToRawControls -> raw controls -> PSD ->
# joint transforms + blend-shape weights + animated maps.
# The addon's interactive path (RigInstance.evaluate) always starts from the face board bones,
# so anything we poke into the raw controls would be overwritten on the next depsgraph tick.
# Epic's own ARKit mapping is authored against the raw control curves (CTRL_expressions.*), and
# the raw layer is 1-D and unambiguous (the GUI layer is 2-D, with several controls packing two
# opposing raws onto +/- of one axis). So we bypass the GUI layer entirely:
#
#     setRawControl(i, v) ... -> manager.calculate(instance) -> push joints + shape keys
#
# To stop the addon's depsgraph handler from re-deriving raw controls from the (neutral) face
# board mid-bake, we hold `window_manager.character_dna.evaluate_dependency_graph` at False for
# the whole run. RigInstance.evaluate() early-returns when that flag is False and - importantly -
# does not touch the flag in that branch, so this is a clean, restorable gate.
#
# SHAPE KEYS - why we do not use the addon's fast path
# ----------------------------------------------------
# RigInstance.update_head_shape_keys() writes the corrective weights through a cached
# `head_shape_key_apply_plan`, which holds a numpy scratch buffer sized to len(key_blocks) at the
# moment the plan was built. Baking ADDS key blocks, so from the second baked shape onward that
# buffer no longer matches the collection and every write dies with "internal error setting the
# array" - silently producing joint-only bakes with no corrective deformation at all.
#
# So we hold our own {channel_index: [ShapeKey]} map, built once from the sidecar that
# the correctives stage wrote, and assign `.value` directly. Individual ShapeKey references
# stay valid as blocks are appended, so this survives the bake. It also removes the special case
# for the 42 blocks whose canonical names exceeded Blender's 63-char ID limit.

import json
import importlib
import bpy
import numpy as np

from . import config
from .config import ADDON_MODULE as _MODULE


def get_instance():
    callbacks = importlib.import_module(f"{_MODULE}.ui.callbacks")
    instance = callbacks.get_active_rig_instance()
    assert instance is not None, "No active Character DNA rig instance."
    return instance


def get_wm_properties():
    utilities = importlib.import_module(f"{_MODULE}.utilities")
    return utilities.get_addon_window_manager_properties()


def activate(obj):
    """Make `obj` the sole selected, active, visible object and return a context override for it.

    Two things bite here. First, the DNA importer leaves both armatures hidden in the view layer,
    and operators poll against visibility, so the object must be unhidden before it can be made
    active. Second, when a script runs after `wm.open_mainfile` (or from the MCP add-on's
    execution context) `bpy.context` can still point at the pre-load window, so assigning
    `view_layer.objects.active` is not enough - operators still report "Context missing active
    object". Passing the override explicitly makes the operator poll pass regardless.

    Usage:
        with riglogic_core.activate(obj):
            bpy.ops.object.mode_set(mode="EDIT")
    """
    obj.hide_set(False)
    obj.hide_viewport = False
    view_layer = bpy.context.view_layer
    for other in view_layer.objects:
        other.select_set(False)
    obj.select_set(True)
    view_layer.objects.active = obj
    return bpy.context.temp_override(
        object=obj,
        active_object=obj,
        selected_objects=[obj],
        selected_editable_objects=[obj],
        view_layer=view_layer,
    )


def invalidate_caches(instance=None):
    """Drop the addon's volatile per-instance caches.

    RigInstance memoises live bpy wrappers - the shape-key apply plan holds `key_blocks`
    collections, the mesh lookup holds Object references. Deleting or renaming a head mesh leaves
    those pointing at removed data and the next evaluate() dies inside foreach_get with a length
    mismatch. Call this after any structural change to the head component.
    """
    instance = instance or get_instance()
    instance.destroy_references()
    for key in list(instance.data.keys()):
        if "shape_key" in key or "mesh_index_lookup" in key or "channel" in key:
            instance.data.pop(key, None)


class RigDriver:
    """Poses the MetaHuman head rig from raw control values and reads back deformed geometry."""

    def __init__(self):
        self.instance = get_instance()
        self.reader = self.instance.head_dna_reader
        self.rig_logic = self.instance.head_instance
        self.manager = self.instance.head_manager

        self.raw_names = [self.reader.getRawControlName(i) for i in range(self.reader.getRawControlCount())]
        # Strip the "CTRL_expressions." prefix for ergonomic mapping tables. The trailing 12
        # entries are the neck/head quaternion channels (neck_01.qx ...), which have no prefix
        # and which we never drive - the head must stay at rest for a VRChat bake.
        self.raw_index = {}
        for index, full_name in enumerate(self.raw_names):
            if full_name.startswith("CTRL_expressions."):
                self.raw_index[full_name.split(".", 1)[1]] = index
            self.raw_index[full_name] = index

        self.head_meshes = self._collect_head_meshes()
        self.corrective_blocks = self._collect_corrective_blocks()
        self._wm = get_wm_properties()
        self._gate_held = False

    # ------------------------------------------------------------------ setup

    def _collect_head_meshes(self):
        """LOD0 head-component mesh objects, in DNA mesh order."""
        lookup = self.instance.head_mesh_index_lookup
        meshes = []
        for mesh_index in self.reader.getMeshIndicesForLOD(0):
            obj = lookup.get(mesh_index)
            if obj is not None:
                meshes.append((mesh_index, self.reader.getMeshName(mesh_index), obj))
        return meshes

    def _collect_corrective_blocks(self):
        """All (channel_index, ShapeKey) corrective pairs, from the correctives-stage sidecar.

        Meshes dropped since the correctives were authored (saliva / eyeshell / cartilage) are
        skipped, so this is safe to rebuild at any point in the pipeline.
        """
        manifest = json.loads(config.get().correctives_sidecar.read_text(encoding="utf-8"))
        blocks = []
        for mesh_entry in manifest["meshes"].values():
            obj = bpy.data.objects.get(mesh_entry["object"])
            if not obj or not obj.data.shape_keys:
                continue
            key_blocks = obj.data.shape_keys.key_blocks
            for channel_index, block_name in mesh_entry["keys"].items():
                block = key_blocks.get(block_name)
                if block is not None:
                    blocks.append((int(channel_index), block))
        return blocks

    # ------------------------------------------------------- evaluation gate

    def __enter__(self):
        self._gate_held = True
        self._wm.evaluate_dependency_graph = False
        self.instance.head_initialize() if not self.instance.head_initialized else None
        return self

    def __exit__(self, *_):
        self.reset()
        self._wm.evaluate_dependency_graph = True
        self._gate_held = False
        return False

    # ------------------------------------------------------------- driving

    def zero_raw_controls(self):
        for index in range(self.rig_logic.getRawControlCount()):
            self.rig_logic.setRawControl(index, 0.0)

    def set_raw_controls(self, values: dict):
        """values: {"jawOpen": 1.0, ...} - names with or without the CTRL_expressions. prefix."""
        unknown = []
        for name, value in values.items():
            index = self.raw_index.get(name)
            if index is None:
                unknown.append(name)
                continue
            self.rig_logic.setRawControl(index, float(value))
        assert not unknown, f"Unknown raw controls: {unknown}"

    def apply(self):
        """Run RigLogic and push its outputs onto the Blender rig + shape keys."""
        self.manager.calculate(self.rig_logic)
        self.instance.update_head_bone_transforms()
        outputs = self.rig_logic.getBlendShapeOutputs()
        for channel_index, block in self.corrective_blocks:
            block.value = outputs[channel_index]
        bpy.context.view_layer.update()

    def pose(self, values: dict):
        """Reset to neutral, then apply exactly `values`."""
        self.zero_raw_controls()
        self.set_raw_controls(values)
        self.apply()

    def reset(self):
        self.zero_raw_controls()
        self.apply()

    # -------------------------------------------------------------- reading

    def evaluated_coords(self, obj) -> np.ndarray:
        """Vertex positions of `obj` after shape keys AND the armature modifier, in object space."""
        depsgraph = bpy.context.evaluated_depsgraph_get()
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        coords = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
        mesh.vertices.foreach_get("co", coords)
        evaluated.to_mesh_clear()
        return coords.reshape(-1, 3)

    def blend_shape_outputs(self) -> dict:
        """Non-zero RigLogic blend-shape channel outputs, keyed by channel name."""
        outputs = self.rig_logic.getBlendShapeOutputs()
        active = {}
        for channel_index, value in enumerate(outputs):
            if abs(value) > 1e-5:
                active[self.reader.getBlendShapeChannelName(channel_index)] = round(float(value), 4)
        return active
