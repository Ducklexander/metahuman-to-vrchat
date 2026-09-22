"""Generate a tileable micro-skin detail normal map (pores + fine wrinkles).

The baked MetaHuman normals resolve pores on the head (4096 px over a head-only UV) but not on the
body (2048 px over the whole body), so the body reads as smooth rubber up close. Poiyomi's
`_DetailNormalMap` tiles a second normal on top of `_BumpMap`, which is the cheap fix.

Everything wraps, so the map tiles without visible seams at any repeat count.
"""

import numpy as np
from PIL import Image
from pathlib import Path


SIZE = 512
PORE_COUNT = 5200
PORE_RADIUS = (1.6, 4.2)     # px
PORE_DEPTH = (0.35, 1.0)
WRINKLE_OCTAVES = 4
WRINKLE_AMPLITUDE = 0.22
NORMAL_STRENGTH = 2.4        # height -> slope gain
SEED = 20260808


def wrapped_gaussian_field(rng):
    """Sum of circular dimples, accumulated with wrap-around so the result tiles."""
    height = np.zeros((SIZE, SIZE), dtype=np.float64)
    ys, xs = np.mgrid[0:SIZE, 0:SIZE]

    cx = rng.integers(0, SIZE, PORE_COUNT)
    cy = rng.integers(0, SIZE, PORE_COUNT)
    rad = rng.uniform(*PORE_RADIUS, PORE_COUNT)
    dep = rng.uniform(*PORE_DEPTH, PORE_COUNT)

    for i in range(PORE_COUNT):
        r = rad[i]
        span = int(np.ceil(r * 2.5))
        y0, y1 = cy[i] - span, cy[i] + span + 1
        x0, x1 = cx[i] - span, cx[i] + span + 1
        yy = np.arange(y0, y1)
        xx = np.arange(x0, x1)
        dy = (yy - cy[i])[:, None]
        dx = (xx - cx[i])[None, :]
        blob = -dep[i] * np.exp(-(dx * dx + dy * dy) / (2.0 * r * r))
        # wrap indices so dimples straddling an edge reappear on the far side
        np.add.at(height, (np.mod(yy, SIZE)[:, None], np.mod(xx, SIZE)[None, :]), blob)
    return height


def wrapped_fbm(rng):
    """Low-amplitude fractal noise from wrapping sine bands -> fine skin wrinkles.

    Both frequencies have to be whole numbers of cycles across the texture, otherwise the band
    does not close on itself and the tile shows a seam. An arbitrary rotation angle breaks that,
    so the direction comes from picking an integer (fx, fy) pair instead.
    """
    ys, xs = np.mgrid[0:SIZE, 0:SIZE].astype(np.float64)
    total = np.zeros((SIZE, SIZE), dtype=np.float64)
    amp = 1.0
    for octave in range(WRINKLE_OCTAVES):
        base = 2 ** (octave + 3)
        for _ in range(2):
            fx = int(rng.integers(1, base + 1))
            fy = int(rng.integers(1, base + 1))
            if rng.random() < 0.5:
                fx = -fx
            phase = rng.uniform(0, 2 * np.pi)
            total += amp * np.sin(2 * np.pi * (fx * xs + fy * ys) / SIZE + phase)
        amp *= 0.5
    total /= np.abs(total).max()
    return total * WRINKLE_AMPLITUDE


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, type=Path)
    OUT = parser.parse_args().out / "Skin_DetailNormal.png"
    rng = np.random.default_rng(SEED)
    height = wrapped_gaussian_field(rng) + wrapped_fbm(rng)
    height -= height.mean()
    height /= max(np.abs(height).max(), 1e-9)

    # Central differences with wrap -> tangent-space normal (OpenGL convention: +Y up)
    dx = (np.roll(height, -1, axis=1) - np.roll(height, 1, axis=1)) * 0.5
    dy = (np.roll(height, -1, axis=0) - np.roll(height, 1, axis=0)) * 0.5

    nx = -dx * NORMAL_STRENGTH
    ny = -dy * NORMAL_STRENGTH
    nz = np.ones_like(nx)
    length = np.sqrt(nx * nx + ny * ny + nz * nz)
    nx, ny, nz = nx / length, ny / length, nz / length

    rgb = np.stack([nx * 0.5 + 0.5, ny * 0.5 + 0.5, nz * 0.5 + 0.5], axis=-1)
    img = (np.clip(rgb, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(img, mode="RGB").save(OUT, optimize=True)

    tilt = np.degrees(np.arccos(np.clip(nz, -1, 1)))
    print(f"wrote {OUT}  ({SIZE}x{SIZE})")
    print(f"  slope angle: mean {tilt.mean():.2f} deg, p99 {np.percentile(tilt, 99):.2f} deg, "
          f"max {tilt.max():.2f} deg")
    print(f"  edge continuity: |left-right| max {np.abs(img[:, 0].astype(int) - img[:, -1].astype(int)).max()}, "
          f"|top-bottom| max {np.abs(img[0].astype(int) - img[-1].astype(int)).max()}")


if __name__ == "__main__":
    main()
