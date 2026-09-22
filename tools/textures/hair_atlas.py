# Author the hair strand atlas (scalp hair, eyelashes, eyebrows) from scratch.
#
#   python tools/textures/hair_atlas.py --params hair_params.json --out <folder>
#
# WHY FROM SCRATCH
# ----------------
# UE's `M_hair_v4` is a procedural strand shader: there is no base colour or alpha atlas anywhere
# in the project to export, and the GroomAsset (the real strands) cannot be exported either
# because UE's Groom plugin registers only an importer. So the atlas has to be authored, and the
# cards have to be re-UV'd onto it (blender stage 08b).
#
# LAYOUT: see blender/mh2vrc/hair_atlas_spec.py (shared with the re-UV stage so they cannot drift).
#
# COLOUR: --params is the JSON written by tools/unreal/export_hair.py, holding the melanin /
# redness / dye values of your MetaHuman's hair-card material instance. Without it a neutral
# brown is used.
#
# ALPHA AND FRINGING
# ------------------
# The RGB is flood-filled outward into the fully transparent pixels at the end. Without that,
# bilinear filtering and mip generation blend hair colour with the black of empty texels and the
# card edges go dark - the classic "black halo" on transparent hair.

import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt, gaussian_filter

import sys

SPEC_DIR = Path(__file__).resolve().parents[2] / "blender" / "mh2vrc"
sys.path.insert(0, str(SPEC_DIR))
from hair_atlas_spec import ALL_ZONES, ATLAS  # noqa: E402

HAIR_PARAMS = OUT_DIR = None  # set from the command line in main()

# How the UE hair parameters are interpreted. MetaHuman's M_hair_v4 is a procedural strand
# shader and this re-creates its look as flat texels, so a literal 1:1 port reads as garish. The
# constants below were tuned on my character (dark hair with blue highlights and a blue ombre);
# tune them for yours if the result is too strong or too weak.
HIGHLIGHT_STRAND_FRACTION = 1.0 / 8.0   # HighlightsVariationNumber = 8
HIGHLIGHT_MIX = 0.55                    # how far a highlight strand moves toward the dye colour
# A literal read of HighlightsMelanin = 0.15 produced near-white streaks that rendered as GREY
# HAIR rather than a blue sheen. Darkened until the highlight reads as a cool glint on black hair.
HIGHLIGHT_VALUE = 0.42
OMBRE_MIX = 0.15                        # OmbreShift 0.3 was too strong on flat texels; halved
DYE_MIX = 0.25                          # restraint on the near-black hairDye

FALLBACK_HAIR_RGB = (0.36, 0.26, 0.17)

RNG = np.random.default_rng(20260807)


def melanin_to_rgb(melanin: float, redness: float) -> np.ndarray:
    """MetaHuman parameterises hair by melanin/redness, not by a literal colour.

    Eumelanin darkens roughly exponentially with concentration; pheomelanin (redness) pushes the
    remaining reflectance toward orange.
    """
    base = float(np.clip(0.85 * np.exp(-2.4 * melanin), 0.03, 0.85))
    red = float(np.clip(redness, 0.0, 1.0))
    return np.array([base, base * (0.72 - 0.15 * red), base * (0.48 - 0.28 * red)], dtype=np.float32)


def load_hair_palette() -> tuple[dict, str]:
    """Build base / highlight / ombre colours from the authored UE parameters."""
    if not HAIR_PARAMS.exists():
        return {"base": np.asarray(FALLBACK_HAIR_RGB, dtype=np.float32),
                "highlight": np.asarray(FALLBACK_HAIR_RGB, dtype=np.float32) * 1.6,
                "ombre": np.asarray(FALLBACK_HAIR_RGB, dtype=np.float32) * 1.3}, "fallback (no UE dump)"

    data = json.loads(HAIR_PARAMS.read_text(encoding="utf-8"))
    # Use the hair-CARDS material instance (not the strand or helmet ones): that is what the
    # card meshes render with in UE.
    # The character's own instance is a MID_* (e.g. MID_MI_Hair_Cards_209); the shared parent
    # MI_Hair_Cards has no melanin values of its own.
    cards = [e for e in data.get("instances", [])
             if "Hair_Cards" in e["asset"] and "hairMelanin" in e.get("scalars", {})]
    cards.sort(key=lambda e: "/MID_" not in e["asset"])
    entry = cards[0] if cards else None
    if entry is None:
        return {"base": np.asarray(FALLBACK_HAIR_RGB, dtype=np.float32),
                "highlight": np.asarray(FALLBACK_HAIR_RGB, dtype=np.float32) * 1.6,
                "ombre": np.asarray(FALLBACK_HAIR_RGB, dtype=np.float32) * 1.3}, "fallback (material not found)"

    scalars, vectors = entry.get("scalars", {}), entry.get("vectors", {})
    base = melanin_to_rgb(scalars.get("hairMelanin", 0.5), scalars.get("hairRedness", 0.25))

    dye = np.asarray(vectors.get("hairDye", [0, 0, 0, 0])[:3], dtype=np.float32)
    base = base * (1.0 - DYE_MIX) + dye * DYE_MIX

    highlight = melanin_to_rgb(scalars.get("HighlightsMelanin", 0.15), scalars.get("hairRedness", 0.25))
    highlight_dye = np.asarray(vectors.get("HighlightshairDye", [0, 0, 0, 0])[:3], dtype=np.float32)
    highlight = (highlight * (1.0 - HIGHLIGHT_MIX) + highlight_dye * HIGHLIGHT_MIX) * HIGHLIGHT_VALUE

    ombre = melanin_to_rgb(scalars.get("OmbreMelanin", 0.25), scalars.get("OmbreRedness", 0.3))
    ombre_dye = np.asarray(vectors.get("OmbrehairDye", [0, 0, 0, 0])[:3], dtype=np.float32)
    ombre = ombre * (1.0 - OMBRE_MIX) + ombre_dye * OMBRE_MIX

    return {"base": base, "highlight": highlight, "ombre": ombre}, (
        f"{entry['asset']} (melanin={scalars.get('hairMelanin')}, redness={scalars.get('hairRedness')})"
    )


def draw_cell(width: int, height: int, strands: int, root_width: float, tip_width: float,
              wander: float, palette: dict, tip_fade: float, tint: float = 1.0,
              highlight_fraction: float = HIGHLIGHT_STRAND_FRACTION,
              ombre_strength: float = OMBRE_MIX, edge_fade_u: float = 0.06) -> np.ndarray:
    """Render one strand bundle as straight-alpha RGBA in [0,1].

    Colour follows the authored MetaHuman look: most strands are the melanin base, one in eight
    (HighlightsVariationNumber) is a blue highlight strand, and every strand drifts toward the
    ombre colour along its length.
    """
    rgba = np.zeros((height, width, 4), dtype=np.float32)
    ys = np.arange(height, dtype=np.float32)
    t = ys / max(height - 1, 1)  # 0 at the root (top of the cell), 1 at the tip
    xs = np.arange(width, dtype=np.float32)[None, :]

    for _ in range(strands):
        start = RNG.uniform(-0.15, 1.15) * width
        drift = RNG.uniform(-wander, wander) * width
        amplitude = RNG.uniform(0.0, 0.45) * wander * width
        frequency = RNG.uniform(0.6, 2.4)
        phase = RNG.uniform(0.0, 2.0 * np.pi)

        centre = start + drift * t + amplitude * np.sin(2.0 * np.pi * frequency * t + phase)
        half = (root_width + (tip_width - root_width) * t) * RNG.uniform(0.7, 1.4) * 0.5

        distance = np.abs(xs - centre[:, None]) / np.maximum(half[:, None], 1e-3)
        coverage = np.clip(1.0 - distance, 0.0, 1.0)
        coverage = coverage * coverage * (3.0 - 2.0 * coverage)  # smoothstep

        # Fade the last `tip_fade` of the strand so cards do not end in a hard line, and take a
        # little off the very root so overlapping cards blend instead of banding.
        fade = np.clip((1.0 - t) / max(tip_fade, 1e-3), 0.0, 1.0)
        fade *= np.clip(t / 0.03, 0.0, 1.0) * 0.15 + 0.85
        coverage *= fade[:, None] * RNG.uniform(0.55, 1.0)

        # One strand in eight is a highlight strand (HighlightsVariationNumber = 8); every strand
        # also drifts toward the ombre colour toward the tip, and roots sit darker than tips.
        strand_colour = palette["highlight"] if RNG.random() < highlight_fraction else palette["base"]
        ombre_ramp = np.clip((t - 0.3) / 0.7, 0.0, 1.0)[:, None]
        along = strand_colour[None, :] * (1.0 - ombre_ramp * ombre_strength) + palette["ombre"][None, :] * (
            ombre_ramp * ombre_strength
        )
        shade = RNG.uniform(0.65, 1.35)
        strand_rgb = (along * tint * shade)[:, None, :] * (0.72 + 0.42 * t)[:, None, None]

        alpha = coverage[..., None]
        rgba[..., :3] = strand_rgb * alpha + rgba[..., :3] * (1.0 - alpha)
        rgba[..., 3:] = coverage[..., None] + rgba[..., 3:] * (1.0 - coverage[..., None])

    # Fade the left and right edges of the cell. Without this a card's alpha stops dead at its own
    # rectangle, and with 936 overlapping brow cards those rectangles read as blocky black slabs
    # rather than as hair. Cheap, and it also helps neighbouring cards blend into one another.
    if edge_fade_u > 0.0:
        u = np.linspace(0.0, 1.0, width, dtype=np.float32)
        edge = np.clip(np.minimum(u, 1.0 - u) / max(edge_fade_u, 1e-4), 0.0, 1.0)
        edge = edge * edge * (3.0 - 2.0 * edge)
        rgba[..., 3] *= edge[None, :]

    return rgba


def linear_to_srgb(rgb: np.ndarray) -> np.ndarray:
    """Encode linear reflectance for storage in an 8-bit sRGB PNG.

    Everything above is computed as physical reflectance - melanin_to_rgb returns a linear value,
    and the strand shading multiplies in linear space. Writing those numbers straight to bytes
    would tag linear data as sRGB, and the renderer would then decode it a second time: the
    hair's 0.094 base became 0.009 in the shader, so the albedo was effectively black and every
    pixel we saw was specular sheen. That is exactly what the first previews showed - silver hair.
    """
    rgb = np.clip(rgb, 0.0, 1.0)
    return np.where(rgb <= 0.0031308, rgb * 12.92, 1.055 * np.power(rgb, 1.0 / 2.4) - 0.055)


def dilate_colour(rgba: np.ndarray, iterations: int = 24) -> np.ndarray:
    """Flood the nearest opaque colour outward so transparent texels are never black."""
    alpha = rgba[..., 3]
    solid = alpha > 0.02
    if not solid.any():
        return rgba
    _, indices = distance_transform_edt(~solid, return_distances=True, return_indices=True)
    filled = rgba.copy()
    filled[..., :3] = rgba[indices[0], indices[1], :3]
    filled[..., :3] = np.where(solid[..., None], rgba[..., :3], filled[..., :3])
    return filled


def main():
    import argparse

    global HAIR_PARAMS, OUT_DIR
    parser = argparse.ArgumentParser(description="Paint the hair / lash / brow strand atlas.")
    parser.add_argument("--params", type=Path, help="hair material parameters JSON from tools/unreal/export_hair.py")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    HAIR_PARAMS = args.params if args.params else Path("__missing__")
    OUT_DIR = args.out
    palette, colour_source = load_hair_palette()

    atlas = np.zeros((ATLAS, ATLAS, 4), dtype=np.float32)

    # Per-zone strand character. Density figures come from an earlier pass where 26-44 strands per
    # hair cell left the card only 22% opaque - visibly see-through; real hair-card art sits nearer
    # 40-55%. Brows and lashes get no highlight or ombre: the blue dye job belongs to the scalp
    # groom, and letting it reach the brows made them look grey-streaked.
    recipes = {
        "hair": dict(strands=(78, 112), root_width=(4.5, 7.5), tip_width=(1.0, 2.0),
                     wander=(0.12, 0.4), tip_fade=(0.18, 0.34), tint=1.0, edge_fade_u=0.06,
                     highlight_fraction=HIGHLIGHT_STRAND_FRACTION, ombre_strength=OMBRE_MIX),
        # Lash and brow cells are much wider in pixels than a hair column (64 and 512 vs 128), so
        # the strand counts have to scale with the cell area or the cards come out see-through:
        # a first pass left the brow zone only 9% opaque, which read as bald patches.
        # Retune after seeing it in Unity: the original density (48-72 strands, 2.2-3.6 px roots) read as a solid
        # black eyeliner smear once 211 lash cards overlapped on the actual lash line - the exact
        # opposite of the fine individual lashes we want. Halved the count and thinned the strands;
        # the lash line now builds its darkness from overlap instead of from each card being opaque.
        "lash": dict(strands=(22, 32), root_width=(1.1, 1.8), tip_width=(0.35, 0.6),
                     wander=(0.2, 0.5), tip_fade=(0.4, 0.62), tint=0.5, edge_fade_u=0.15,
                     highlight_fraction=0.0, ombre_strength=0.0),
        # Brows deliberately sit LOWEST in opacity, with the finest strands and the widest edge
        # fade. 936 brow cards cover a very small patch of face and overlap many times over, so
        # anything approaching a solid card stacks into a painted-on black slab with visible
        # rectangular edges - which is exactly what the first textured preview showed.
        # Retune after seeing it in Unity: with the Hair material on TransClipping (alpha blend, cutoff 0.01)
        # every faint strand now contributes instead of being clipped away, so 936 overlapping brow
        # cards stacked into a solid slab with the card rectangles showing through - the same
        # failure mode as the first pass, just reached from the other direction. Roughly halved the
        # strand count and widened the horizontal edge fade so the cell borders dissolve.
        "brow": dict(strands=(230, 310), root_width=(1.15, 1.85), tip_width=(0.45, 0.8),
                     wander=(0.35, 0.8), tip_fade=(0.36, 0.60), tint=0.58, edge_fade_u=0.28,
                     highlight_fraction=0.0, ombre_strength=0.0),
    }

    for name, zone in ALL_ZONES.items():
        recipe = recipes[name]
        top, bottom = zone["rows"]
        for column in range(zone["columns"]):
            x0 = column * zone["cell_width"]
            atlas[top:bottom, x0 : x0 + zone["cell_width"]] = draw_cell(
                zone["cell_width"], zone["cell_height"],
                strands=int(RNG.integers(*recipe["strands"])),
                root_width=RNG.uniform(*recipe["root_width"]),
                tip_width=RNG.uniform(*recipe["tip_width"]),
                wander=RNG.uniform(*recipe["wander"]),
                palette=palette,
                tip_fade=RNG.uniform(*recipe["tip_fade"]),
                tint=recipe["tint"],
                highlight_fraction=recipe["highlight_fraction"],
                ombre_strength=recipe["ombre_strength"],
                edge_fade_u=recipe["edge_fade_u"],
            )

    # A whisper of blur removes the aliasing that per-row strand rasterisation leaves behind,
    # without softening the strands into mush.
    atlas[..., 3] = gaussian_filter(atlas[..., 3], 0.6)
    atlas = dilate_colour(atlas)
    atlas[..., :3] = linear_to_srgb(atlas[..., :3])

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / "Hair_BaseColor.png"
    Image.fromarray((np.clip(atlas, 0, 1) * 255 + 0.5).astype(np.uint8), mode="RGBA").save(path, optimize=True)

    result = {
        "file": str(path),
        "size": [ATLAS, ATLAS],
        "zones": {
            name: {**{k: zone[k] for k in ("rows", "columns", "cell_width", "cell_height", "aspect",
                                           "v_low", "v_high")},
                   "opaque_fraction": round(
                       float((atlas[zone["rows"][0] : zone["rows"][1], ..., 3] > 0.5).mean()), 4)}
            for name, zone in ALL_ZONES.items()
        },
        "palette": {k: [round(float(c), 4) for c in v] for k, v in palette.items()},
        "hair_colour_source": colour_source,
        "bytes": path.stat().st_size,
    }
    (OUT_DIR / "hair_atlas_result.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    print(json.dumps(result, indent=1))


if __name__ == "__main__":
    main()
