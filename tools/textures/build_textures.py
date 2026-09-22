# Build the shipping texture set (skin, eyes, teeth) from the textures you exported from UE.
#
# Runs on plain CPython 3.10+ with Pillow, numpy and scipy (pip install -r requirements.txt).
# No Blender needed.
#
#   python tools/textures/build_textures.py --src <UE Textures folder> --dcc <FaceTextures folder> --out <folder>
#
# --src   the baked textures exported from the UE project (T_Head_BC.png, T_Head_N.png, ...)
# --dcc   MetaHuman Character > Save Face Textures (needs the *_Cavity.png)
#
# WHAT COMES OUT, PER MATERIAL SLOT
#   Skin_Head / Skin_Body   <slot>_BaseColor.png  2048  sRGB
#                           <slot>_Normal.png     2048  linear, GREEN FLIPPED
#                           <slot>_Mask.png       2048  linear, packed (see MASK PACKING)
#   Eye_L / Eye_R           Eye_<side>_BaseColor.png 1024 sRGB   (iris composited onto sclera)
#                           Eye_<side>_Normal.png    1024 linear, green flipped
#   Teeth_Tongue            Teeth_BaseColor.png   1024 sRGB
#                           Teeth_Normal.png      1024 linear, green flipped
#                           Teeth_Mask.png        1024 linear, packed
#
# GREEN FLIP - not a guess
# ------------------------
# Unreal authors tangent normals in the DirectX convention (green = down), Unity/Blender want
# OpenGL (green = up). I confirmed this on the actual files rather than trusting doctrine
# (the test is described in docs/04-textures.md): skin is pit-dominated, so laplacian(h) must be positively skewed, and
# the horizontal term of the laplacian - which does not depend on the convention at all - serves
# as a built-in validity control. T_Head_N scored control +0.239 with DirectX +0.202 vs OpenGL
# -0.018; T_Body_N scored control +0.408 with DirectX +4.48 vs OpenGL -3.26. Both authored
# DirectX, so every normal map here gets its green channel inverted.
#
# MASK PACKING
# ------------
# Poiyomi does not mandate a packing - every map slot (Metallic, Smoothness, AO) has its own
# channel dropdown - so we choose one layout and document it:
#     R = Metallic     (MetaHuman skin is dielectric; this is flat 0, kept so the channel exists)
#     G = Smoothness   (1 - roughness, from SRMF.G)
#     B = AO           (from the Cavity map, remapped - see below)
#     A = SSS mask     (the Scatter map; drives Poiyomi's subsurface if enabled)
# Source SRMF channel semantics, confirmed against the inventory: R=Specular, G=Roughness,
# B=Metallic (measured constant, as expected for skin), A=Fuzz.
#
# The MetaHuman cavity map is nearly black (mean 0.185) and is a micro-detail map rather than a
# classic white-flat/dark-crevice AO map, so feeding it in raw would crush the whole face. It is
# remapped to sit just under white and only darken the actual crevices.

import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

Image.MAX_IMAGE_PIXELS = None

SRC = DCC = OUT = None  # set from the command line in main()

# Per-map sizes rather than one global number, because the budget should follow what the viewer
# actually looks at. This project's whole point is the face, and VRChat users spend most of their
# time in a mirror at close range, so the head normal keeps 4K (the source is 8K) while the body -
# which nobody inspects up close - stays at 2K and its mask drops to 1K. The full set lands around
# 62 MB of VRAM, inside VRChat's "Good" texture-memory band (<= 75 MB).
HEAD_BASECOLOR_SIZE = 2048   # source T_Head_BC is only 2048, so there is nothing to gain above it
HEAD_NORMAL_SIZE = 4096
HEAD_MASK_SIZE = 2048
BODY_BASECOLOR_SIZE = 2048
BODY_NORMAL_SIZE = 2048
BODY_MASK_SIZE = 1024
EYE_SIZE = 1024
TEETH_SIZE = 1024

# How far the cavity map is allowed to darken the AO channel. 0.35 keeps creases readable without
# turning the face muddy.
CAVITY_AO_STRENGTH = 0.35

REQUIRED_SOURCES = [
    "T_Head_BC.png", "T_Head_N.png", "T_Head_SRMF.png", "T_Head_Scatter.png",
    "T_Body_BC.png", "T_Body_N.png", "T_Body_SRMF.png", "T_Body_Scatter.png",
    "T_EyeIrisL_BC.png", "T_EyeIrisL_N.png", "T_EyeScleraL_BC.png", "T_EyeScleraL_N.png",
    "T_EyeIrisR_BC.png", "T_EyeIrisR_N.png", "T_EyeScleraR_BC.png", "T_EyeScleraR_N.png",
    "T_Teeth_BC.png", "T_Teeth_N.png", "T_Teeth_SRM.png",
]


def load(path: Path, size=None, mode="RGB") -> np.ndarray:
    with Image.open(path) as image:
        image = image.convert(mode)
        if size and image.size != (size, size):
            image = image.resize((size, size), Image.LANCZOS)
        return np.asarray(image, dtype=np.float32) / 255.0


def save(array: np.ndarray, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = np.clip(array, 0.0, 1.0)
    image = Image.fromarray((data * 255.0 + 0.5).astype(np.uint8))
    image.save(path, optimize=True)
    return {"file": path.name, "size": list(image.size), "mode": image.mode,
            "bytes": path.stat().st_size}


def flip_green(normal: np.ndarray) -> np.ndarray:
    out = normal.copy()
    out[..., 1] = 1.0 - out[..., 1]
    return out


def find_cavity() -> Path:
    """MetaHuman names the file after the character (<Name>_Cavity.png)."""
    matches = sorted(DCC.glob("*Cavity*.png"))
    assert matches, f"no *_Cavity.png in {DCC} - export it with MetaHuman Character > Save Face Textures"
    return matches[0]


def build_thickness(slot: str, mask_path: Path, size: int = 512) -> dict:
    """Poiyomi's Skin lighting mode reads a thickness map's R channel, but the subsurface mask is
    packed into the Mask's A channel. Pull it out as a small greyscale map, and set
    _SkinThicknessMapInvert = 1 on the material so subsurface = map.r."""
    with Image.open(mask_path) as image:
        alpha = image.getchannel("A").resize((size, size), Image.LANCZOS)
    path = OUT / f"{slot}_Thickness.png"
    alpha.save(path, optimize=True)
    return {"file": path.name, "size": [size, size], "mode": "L", "bytes": path.stat().st_size}


def build_ao_from_cavity(size: int) -> np.ndarray:
    """Remap MetaHuman's very dark cavity map into a usable AO channel.

    The raw map has mean 0.185. Normalising by its own high percentile and then lerping from
    white by CAVITY_AO_STRENGTH keeps flat skin at ~1.0 and only pushes the crevices down.
    """
    cavity = load(find_cavity(), size).mean(axis=2)
    high = float(np.percentile(cavity, 98))
    normalised = np.clip(cavity / max(high, 1e-4), 0.0, 1.0)
    return 1.0 - CAVITY_AO_STRENGTH * (1.0 - normalised)


def build_skin(slot: str, basecolor: Path, normal: Path, srmf: Path, scatter: Path,
               ao_source: Path | None, sizes: dict) -> list:
    written = []
    written.append(save(load(basecolor, sizes["basecolor"]), OUT / f"{slot}_BaseColor.png"))
    written.append(save(flip_green(load(normal, sizes["normal"])), OUT / f"{slot}_Normal.png"))

    size = sizes["mask"]
    srmf_rgba = load(srmf, size, mode="RGBA")
    roughness = srmf_rgba[..., 1]
    metallic = srmf_rgba[..., 2]
    scatter_map = load(scatter, size).mean(axis=2)
    ao = build_ao_from_cavity(size) if ao_source else None

    mask = np.stack([
        metallic,                                   # R - flat 0 for skin, kept for completeness
        1.0 - roughness,                            # G - smoothness
        ao if ao is not None else np.ones_like(roughness),  # B - AO
        scatter_map,                                # A - subsurface mask
    ], axis=2)
    written.append(save(mask, OUT / f"{slot}_Mask.png"))
    written.append(build_thickness(slot, OUT / f"{slot}_Mask.png"))
    return written


# The iris map has no dark surround to detect an edge against - its radial profile is essentially
# flat from r=0.5 all the way past the corners, i.e. the iris art fills the frame. The visible
# fibre disc ends at roughly 0.92 of the half-width, with the limbus ring beyond it.
IRIS_ART_RADIUS = 0.92
# Saturation threshold that separates the sclera map's desaturated limbus disc (sat ~0.02) from
# the veined white sclera around it (sat rises past 0.05 by r~0.31).
LIMBUS_SATURATION = 0.05


def radial_grid(shape):
    height, width = shape[:2]
    yy, xx = np.mgrid[0:height, 0:width]
    cy, cx = (height - 1) / 2.0, (width - 1) / 2.0
    return np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2) / (min(height, width) / 2.0), yy, xx, cy, cx


def measure_limbus_radius(sclera: np.ndarray) -> float:
    """Radius where the sclera map stops being desaturated, i.e. the edge of its iris hole."""
    radius, *_ = radial_grid(sclera.shape)
    saturation = sclera.max(axis=2) - sclera.min(axis=2)
    bins = np.linspace(0.0, 1.0, 101)
    index = np.clip(np.digitize(radius, bins) - 1, 0, len(bins) - 2)
    for i in range(len(bins) - 1):
        selected = index == i
        if selected.any() and float(saturation[selected].mean()) > LIMBUS_SATURATION:
            return float(bins[i])
    return 0.31


def build_eye(side: str, size: int) -> tuple[list, dict]:
    """Composite MetaHuman's separate iris and sclera maps into one base colour.

    UE's eye shader keeps them apart and blends with a radial mask plus refraction; Poiyomi needs
    a single albedo. Both maps share the eyeball's planar UV, so the compositing is radial: the
    sclera is the base, and the iris is scaled so its outer edge lands on the limbus ring that the
    sclera map already marks, then blended in with a soft edge.
    """
    iris = load(SRC / f"T_EyeIris{side}_BC.png", size)
    sclera = load(SRC / f"T_EyeSclera{side}_BC.png", size)

    iris_radius = IRIS_ART_RADIUS
    limbus_radius = measure_limbus_radius(sclera)

    radius, yy, xx, cy, cx = radial_grid(sclera.shape)
    height, width = sclera.shape[:2]

    # Resample the iris so its art edge lands exactly on the sclera map's limbus ring.
    scale = iris_radius / max(limbus_radius, 1e-3)
    source_y = np.clip((yy - cy) * scale + cy, 0, height - 1).astype(np.int32)
    source_x = np.clip((xx - cx) * scale + cx, 0, width - 1).astype(np.int32)
    iris_scaled = iris[source_y, source_x]

    feather = 0.05
    blend = np.clip((limbus_radius - radius) / feather, 0.0, 1.0)[..., None]
    blend = gaussian_filter(blend, (2, 2, 0))
    composite = iris_scaled * blend + sclera * (1.0 - blend)

    written = [save(composite, OUT / f"Eye_{side}_BaseColor.png")]

    # Same treatment for the normals, then the shared green flip.
    iris_n = load(SRC / f"T_EyeIris{side}_N.png", size)[source_y, source_x]
    sclera_n = load(SRC / f"T_EyeSclera{side}_N.png", size)
    normal = iris_n * blend + sclera_n * (1.0 - blend)
    written.append(save(flip_green(normal), OUT / f"Eye_{side}_Normal.png"))

    return written, {"iris_radius": round(iris_radius, 4), "limbus_radius": round(limbus_radius, 4),
                     "iris_scale": round(scale, 4)}


def build_teeth(size: int) -> list:
    written = [save(load(SRC / "T_Teeth_BC.png", size), OUT / "Teeth_BaseColor.png")]
    written.append(save(flip_green(load(SRC / "T_Teeth_N.png", size)), OUT / "Teeth_Normal.png"))

    srm = load(SRC / "T_Teeth_SRM.png", size, mode="RGBA")
    roughness = srm[..., 1]
    mask = np.stack([
        np.zeros_like(roughness),
        1.0 - roughness,
        np.ones_like(roughness),
        np.ones_like(roughness),
    ], axis=2)
    written.append(save(mask, OUT / "Teeth_Mask.png"))
    return written


def main():
    import argparse

    global SRC, DCC, OUT
    parser = argparse.ArgumentParser(description="Build the shipping skin/eye/teeth textures.")
    parser.add_argument("--src", required=True, type=Path, help="UE-exported baked textures")
    parser.add_argument("--dcc", required=True, type=Path, help="Save Face Textures output (has *_Cavity.png)")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    SRC, DCC, OUT = args.src, args.dcc, args.out
    missing = [n for n in REQUIRED_SOURCES if not (SRC / n).is_file()]
    assert not missing, f"missing in {SRC}: {missing}"
    OUT.mkdir(parents=True, exist_ok=True)
    result = {"green_flip_applied": True, "cavity_ao_strength": CAVITY_AO_STRENGTH, "files": []}

    result["files"] += build_skin(
        "Skin_Head", SRC / "T_Head_BC.png", SRC / "T_Head_N.png", SRC / "T_Head_SRMF.png",
        SRC / "T_Head_Scatter.png", find_cavity(),
        {"basecolor": HEAD_BASECOLOR_SIZE, "normal": HEAD_NORMAL_SIZE, "mask": HEAD_MASK_SIZE},
    )
    # The body has its own UV layout, so the head's cavity-derived AO does not apply to it; its
    # AO channel is left flat white.
    result["files"] += build_skin(
        "Skin_Body", SRC / "T_Body_BC.png", SRC / "T_Body_N.png", SRC / "T_Body_SRMF.png",
        SRC / "T_Body_Scatter.png", None,
        {"basecolor": BODY_BASECOLOR_SIZE, "normal": BODY_NORMAL_SIZE, "mask": BODY_MASK_SIZE},
    )

    result["eyes"] = {}
    for side in ("L", "R"):
        written, stats = build_eye(side, EYE_SIZE)
        result["files"] += written
        result["eyes"][side] = stats

    result["files"] += build_teeth(TEETH_SIZE)

    (OUT / "texture_build_result.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    total = sum(f["bytes"] for f in result["files"])
    print(json.dumps({"files": len(result["files"]), "png_bytes_total_mb": round(total / 1048576, 2),
                      "eyes": result["eyes"], "out": str(OUT)}, indent=1))


if __name__ == "__main__":
    main()
