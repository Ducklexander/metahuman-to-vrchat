# Deterministic head snapshots for visual QA.
#
# Uses a dedicated camera + the Workbench engine rather than an OpenGL viewport grab: it needs no
# 3D-view context (so it works over MCP), renders identically every time, and flat single-colour
# shading with studio lighting reads deformation far more clearly than the MetaHuman skin shader.

from pathlib import Path

import bpy
import numpy as np

CAM_NAME = "QA_Camera"
# Objects that belong to the face board / GUI rig rather than the character.
GUI_PREFIXES = ("CTRL_", "TEXT_", "FRM_", "GRP_", "LOC_", "head_face_gui")


def hide_gui(hide=True):
    for obj in bpy.data.objects:
        if obj.name.startswith(GUI_PREFIXES):
            obj.hide_render = hide
            obj.hide_viewport = hide


def setup(resolution=700):
    """Create/refresh the QA camera and switch the scene to flat Workbench rendering."""
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    shading = scene.display.shading
    shading.light = "STUDIO"
    shading.color_type = "SINGLE"
    shading.single_color = (0.72, 0.68, 0.66)
    # Cavity/curvature shading turns the 24k-vert MetaHuman skin into speckled noise that hides
    # the very deformation we are checking - plain studio lighting reads far better here.
    shading.show_cavity = False
    shading.show_specular_highlight = True
    scene.display.render_aa = "8"
    scene.render.resolution_x = resolution
    scene.render.resolution_y = resolution
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = "PNG"

    hide_gui(True)

    cam = bpy.data.objects.get(CAM_NAME)
    if cam is None:
        cam_data = bpy.data.cameras.new(CAM_NAME)
        cam = bpy.data.objects.new(CAM_NAME, cam_data)
        scene.collection.objects.link(cam)
    cam.data.type = "PERSP"
    cam.data.lens = 85.0
    scene.camera = cam
    return cam


# Measured from the imported LOD0 head: the skull spans z 1.321-1.681 with the face pointing -Y,
# so this sits the framing on the mid-face rather than the cranium.
FACE_TARGET = (0.0, -0.045, 1.545)


def aim(target=FACE_TARGET, distance=0.42, azimuth=0.0, elevation=0.0):
    """Point the QA camera at `target` from a spherical offset.

    azimuth/elevation are degrees; azimuth 0 = straight-on front view (-Y looking toward +Y),
    positive azimuth orbits toward the character's left.
    """
    import math

    from mathutils import Euler, Vector

    cam = setup() if bpy.data.objects.get(CAM_NAME) is None else bpy.data.objects[CAM_NAME]
    az, el = math.radians(azimuth), math.radians(elevation)
    offset = Vector((-math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el))) * distance
    cam.location = Vector(target) + offset
    # Camera looks down its local -Z; rotate from that to the target direction.
    direction = (Vector(target) - cam.location).normalized()
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    return cam


def render(path, only=None):
    """Render to `path`. `only` = iterable of object names to show (others hidden from render)."""
    scene = bpy.context.scene
    restore = {}
    if only is not None:
        keep = set(only)
        for obj in bpy.data.objects:
            if obj.type != "MESH":
                continue
            restore[obj.name] = obj.hide_render
            obj.hide_render = obj.name not in keep

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)

    for name, value in restore.items():
        bpy.data.objects[name].hide_render = value
    return str(path)


# The visible head assembly for face QA: skin, teeth/tongue, eyes, lashes, eye shell/edge.
FACE_PARTS = [
    "head_head_lod0_mesh",
    "head_teeth_lod0_mesh",
    "head_eyeLeft_lod0_mesh",
    "head_eyeRight_lod0_mesh",
    "head_eyeshell_lod0_mesh",
    "head_eyelashes_lod0_mesh",
    "head_eyeEdge_lod0_mesh",
]
