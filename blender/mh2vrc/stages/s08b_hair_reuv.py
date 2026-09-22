# Stage 08b - re-UV the hair and eyebrow cards onto the authored strand atlas.
#
# Measured on the LOD1 meshes of my run: MetaHuman gives every card its own private sliver of UV
# space (hair: 1153 cards, median island 0.045 x 0.476; brows: 936 cards, median island 0.25 x
# 0.26) instead of all cards sharing one strand strip. So no ready-made atlas can just be assigned
# - each island has to be remapped onto a strand cell.
#
# The atlas layout (2048^2, three zones: hair / lash / brow, each with a cell aspect matched to
# the measured card-island aspect) is defined once in hair_atlas_spec.py and shared with
# tools/textures/hair_atlas.py, which paints it.
# In every zone the strand ROOT is drawn at the top of the cell, i.e. at HIGH V.
#
# ROOT ORIENTATION - the part that is easy to get silently wrong
# --------------------------------------------------------------
# Nothing guarantees which end of a card's UV island is the root. Get it backwards and the
# transparent, wispy tips end up buried in the scalp while the opaque roots stick out into the
# air - very visible. So the root end is detected from GEOMETRY, not assumed: a card's root is
# the end nearer the head, so we split each island at its V midpoint, measure how far each half
# sits from the head centroid, and flip V when the low-V half turns out to be the near one.
#
# Runs inside Blender, after the cards are imported (stage 08) and before the merge (stage 09).

import json
from collections import defaultdict

import bpy
import numpy as np

from .. import config
from ..hair_atlas_spec import ALL_ZONES, ATLAS
from .s08_hair_and_body import BROW_MESH, HAIR_MESH

# Inset so bilinear filtering and mip generation never bleed a neighbouring column in.
PADDING_U = 1.5 / ATLAS

# The eyelash mesh turns out to be built the same way as the card meshes - 211 thin strips with
# per-card UV islands (median 0.017 x 0.117, aspect 6.4:1) - and lashes are hair, so they get
# their own atlas zone rather than a separate material and texture. That drops the avatar from
# 8 material slots to 7.
TARGETS = {
    HAIR_MESH: "hair",
    BROW_MESH: "brow",
    "head_eyelashes_lod0_mesh": "lash",
}

RNG = None  # seeded from the config in main() so re-runs produce identical UVs


def loose_parts(mesh) -> list[np.ndarray]:
    parent = np.arange(len(mesh.vertices))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    edges = np.empty(len(mesh.edges) * 2, dtype=np.int32)
    mesh.edges.foreach_get("vertices", edges)
    for a, b in edges.reshape(-1, 2):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    groups = defaultdict(list)
    for index in range(len(mesh.vertices)):
        groups[find(index)].append(index)
    return [np.asarray(v, dtype=np.int32) for v in groups.values()]


def reuv(obj, zone_name: str) -> dict:
    zone = ALL_ZONES[zone_name]
    mesh = obj.data
    uv_layer = mesh.uv_layers[0]

    uvs = np.empty(len(mesh.loops) * 2, dtype=np.float32)
    uv_layer.uv.foreach_get("vector", uvs)
    uvs = uvs.reshape(-1, 2)

    loop_vertex = np.empty(len(mesh.loops), dtype=np.int32)
    mesh.loops.foreach_get("vertex_index", loop_vertex)

    positions = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
    mesh.vertices.foreach_get("co", positions)
    positions = positions.reshape(-1, 3)

    # The scalp reference: cards hang off the head, so the mesh's own centre of mass is a good
    # stand-in for "toward the skull". For the lash strips the same logic holds - the root end is
    # the one on the lid.
    centroid = positions.mean(axis=0)

    parts = loose_parts(mesh)
    v_low, v_high = zone["v_low"], zone["v_high"]
    columns = zone["columns"]
    flipped = 0

    for index, vertex_indices in enumerate(parts):
        member = np.isin(loop_vertex, vertex_indices)
        if not member.any():
            continue
        island = uvs[member]
        u0, v0 = island.min(axis=0)
        u1, v1 = island.max(axis=0)
        u_span = max(u1 - u0, 1e-6)
        v_span = max(v1 - v0, 1e-6)

        # Which end of this island is the root?
        mid_v = 0.5 * (v0 + v1)
        low_vertices = np.unique(loop_vertex[member][island[:, 1] <= mid_v])
        high_vertices = np.unique(loop_vertex[member][island[:, 1] > mid_v])
        flip = False
        if low_vertices.size and high_vertices.size:
            low_distance = np.linalg.norm(positions[low_vertices] - centroid, axis=1).mean()
            high_distance = np.linalg.norm(positions[high_vertices] - centroid, axis=1).mean()
            # Root = nearer the head. The atlas puts the root at high V, so flip when the low-V
            # half is the near one.
            flip = low_distance < high_distance
        flipped += int(flip)

        column = int(RNG.integers(0, columns))
        cell_u0 = column / columns + PADDING_U
        cell_u1 = (column + 1) / columns - PADDING_U

        normalised = (island - np.array([u0, v0])) / np.array([u_span, v_span])
        if flip:
            normalised[:, 1] = 1.0 - normalised[:, 1]

        uvs[member, 0] = cell_u0 + normalised[:, 0] * (cell_u1 - cell_u0)
        uvs[member, 1] = v_low + normalised[:, 1] * (v_high - v_low)

    uv_layer.uv.foreach_set("vector", uvs.ravel())
    mesh.update()

    return {"object": obj.name, "zone": zone_name, "cards": len(parts), "flipped_v": flipped,
            "zone_v": [round(v_low, 4), round(v_high, 4)], "columns": columns}


def main():
    global RNG
    RNG = np.random.default_rng(config.get().atlas_seed)
    result = {"atlas": {"size": ATLAS, "zones": ALL_ZONES}, "meshes": [], "skipped": []}
    for name, zone_name in TARGETS.items():
        obj = bpy.data.objects.get(name)
        if obj is None:
            # hair_fbx / eyebrow_fbx are optional; the lashes always come from the DNA.
            assert name != "head_eyelashes_lod0_mesh", "eyelash mesh missing - did stage 01 run?"
            result["skipped"].append(name)
            continue
        result["meshes"].append(reuv(obj, zone_name))

    config.get().reuv_result.write_text(json.dumps(result, indent=1), encoding="utf-8")
    return result


if __name__ == "__main__":
    main()
