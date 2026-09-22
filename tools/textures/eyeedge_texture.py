# Author the tear-line (EyeEdge) texture.
#
#   python tools/textures/eyeedge_texture.py --out <folder>
#
# MetaHuman ships no texture for this mesh - UE shades it procedurally, like the hair. It is the
# thin wet strip where the lid meets the eyeball: 386 tris in two strips, a couple of pixels tall
# on screen even in a mirror.
#
# Deliberately UNIFORM rather than a gradient. The mesh has only two loose parts and their UV
# orientation is not something we can verify cheaply, so a gradient has a coin-flip chance of
# running the wrong way and putting the opaque end where the transparent one belongs. A flat
# translucent dark red reads correctly whichever way the strips are laid out, and at this size
# nothing is lost.
#
# The eyelashes are NOT handled here: they turned out to be 211 thin per-card strips just like the
# hair cards, so they were folded into the hair atlas instead (see blender stage 08b).

import json
from pathlib import Path

import numpy as np
from PIL import Image


SIZE = 64
# Dark desaturated red-brown, the colour of the wet lid margin, at partial opacity so it reads as
# a moist line rather than an eyeliner stroke.
COLOUR = (0.22, 0.10, 0.09)
ALPHA = 0.62


def linear_to_srgb(rgb):
    """COLOUR is a linear reflectance; an 8-bit PNG read as sRGB needs it encoded first."""
    rgb = np.clip(rgb, 0.0, 1.0)
    return np.where(rgb <= 0.0031308, rgb * 12.92, 1.055 * np.power(rgb, 1.0 / 2.4) - 0.055)


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, type=Path)
    OUT = parser.parse_args().out / "EyeEdge_BaseColor.png"
    rgba = np.zeros((SIZE, SIZE, 4), dtype=np.float32)
    rgba[..., :3] = linear_to_srgb(np.asarray(COLOUR, dtype=np.float32))
    rgba[..., 3] = ALPHA

    OUT.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray((rgba * 255 + 0.5).astype(np.uint8), mode="RGBA").save(OUT, optimize=True)
    print(json.dumps({"file": str(OUT), "size": [SIZE, SIZE], "colour": COLOUR, "alpha": ALPHA,
                      "bytes": OUT.stat().st_size}, indent=1))


if __name__ == "__main__":
    main()
