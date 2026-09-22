# Stage 05 (optional, --qa) - render contact sheets of baked shapes for human inspection.
#
# Renders each named shape key at 1.0 (rig at rest, correctives at 0 - i.e. exactly what Unity
# will see) and tiles the results into one PNG. Runs right after the bake, while the DNA meshes are
# still separate objects. Sheets land in <work_dir>/qa/. They show your MetaHuman's face: fine to
# post as images, but keep them out of git (work/ is ignored).

from pathlib import Path

import bpy
import numpy as np

from .. import bake_expressions, config, snapshot
from .s08_hair_and_body import BROW_MESH

# Works both before the merge (separate DNA meshes) and after it (single `Body`); names that are
# not in the scene are skipped.
BAKED_MESHES = [
    "Body",
    "head_head_lod0_mesh",
    "head_teeth_lod0_mesh",
    "head_eyeLeft_lod0_mesh",
    "head_eyeRight_lod0_mesh",
    "head_eyelashes_lod0_mesh",
    "head_eyeEdge_lod0_mesh",
    BROW_MESH,
]


def set_shape(values: dict):
    """Set the named baked shapes on every mesh that carries them; zero all other baked keys."""
    for name in BAKED_MESHES:
        obj = bpy.data.objects.get(name)
        if not obj or not obj.data.shape_keys:
            continue
        for block in obj.data.shape_keys.key_blocks:
            if block.name in values:
                block.value = values[block.name]
    bpy.context.view_layer.update()


def clear_shapes(names):
    for mesh_name in BAKED_MESHES:
        obj = bpy.data.objects.get(mesh_name)
        if not obj or not obj.data.shape_keys:
            continue
        for name in names:
            block = obj.data.shape_keys.key_blocks.get(name)
            if block:
                block.value = 0.0
    bpy.context.view_layer.update()


def contact_sheet(entries, out_path, columns=4, tile=360, distance=0.42, azimuth=0.0):
    """entries: list of (label, {shape_name: value}). Returns the written path."""
    snapshot.setup(resolution=tile)
    snapshot.aim(distance=distance, azimuth=azimuth)

    tmp = Path(out_path).with_suffix(".tile.png")
    tiles = []
    for _label, values in entries:
        set_shape(values)
        snapshot.render(str(tmp), only=snapshot.FACE_PARTS)
        image = bpy.data.images.load(str(tmp), check_existing=False)
        pixels = np.array(image.pixels[:], dtype=np.float32).reshape(image.size[1], image.size[0], 4)
        tiles.append(pixels[::-1])  # Blender images are bottom-up
        bpy.data.images.remove(image)
        clear_shapes(values)

    rows = (len(tiles) + columns - 1) // columns
    sheet = np.zeros((rows * tile, columns * tile, 4), dtype=np.float32)
    sheet[..., 3] = 1.0
    for index, pixels in enumerate(tiles):
        r, c = divmod(index, columns)
        sheet[r * tile : (r + 1) * tile, c * tile : (c + 1) * tile] = pixels

    out = bpy.data.images.new("contact_sheet", width=sheet.shape[1], height=sheet.shape[0], alpha=True)
    out.pixels = sheet[::-1].ravel()
    out.filepath_raw = str(out_path)
    out.file_format = "PNG"
    out.save()
    bpy.data.images.remove(out)
    tmp.unlink(missing_ok=True)
    return str(out_path)


ARKIT_SPOTCHECK = [
    ("neutral", {}),
    ("jawOpen", {"jawOpen": 1}),
    ("mouthSmileLeft", {"mouthSmileLeft": 1}),
    ("eyeBlinkLeft", {"eyeBlinkLeft": 1}),
    ("browInnerUp", {"browInnerUp": 1}),
    ("browDownLeft", {"browDownLeft": 1}),
    ("mouthPucker", {"mouthPucker": 1}),
    ("mouthFunnel", {"mouthFunnel": 1}),
    ("noseSneerLeft", {"noseSneerLeft": 1}),
    ("cheekPuff", {"cheekPuff": 1}),
    ("mouthStretchLeft", {"mouthStretchLeft": 1}),
    ("eyeWideLeft", {"eyeWideLeft": 1}),
    ("mouthClose+jawOpen", {"mouthClose": 1, "jawOpen": 1}),
    ("tongueOut+jawOpen", {"tongueOut": 1, "jawOpen": 1}),
    ("TongueUp+jawOpen", {"TongueUp": 1, "jawOpen": 1}),
    ("MH_EyeLidPressLeft", {"MH_EyeLidPressLeft": 1}),
]


def main():
    out_dir = config.get().qa_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    visemes = [(name, {name: 1}) for name in bake_expressions.GROUPS["Visemes"]]
    emotions = [(name, {name: 1}) for name in bake_expressions.GROUPS["Emotions"]]
    written = [
        contact_sheet(ARKIT_SPOTCHECK, out_dir / "sheet_arkit_spotcheck.png"),
        contact_sheet(visemes, out_dir / "sheet_visemes.png", columns=5),
        contact_sheet(emotions, out_dir / "sheet_emotions.png"),
    ]
    return {"sheets": written}
