# The single definition of the hair atlas layout.
#
# Imported by both tools/textures/hair_atlas.py (which paints it, under CPython) and stage 08b
# (which maps cards onto it, inside Blender), so the two can never drift apart.
#
# Every zone's cell aspect is chosen to match the measured UV-island aspect of the cards that go
# into it. That matters: the re-UV maps a card's island bounding box onto a cell rect, so a cell
# whose aspect differs from the card's stretches the strand art. The first attempt put the brow
# cards (island aspect ~1.06) into 128x512 cells (aspect 4) and the strands came out squashed into
# thick blocky tufts.
#
# Measured island aspects in my run (hair and brow cards, plus the lash measurement off the merged
# mesh):  hair 10.3   lashes 6.4   brows 1.06
#
# ATLAS 2048 x 2048, RGBA. V is measured with image row 0 at V = 1.0, and every zone paints the
# strand ROOT at its top, i.e. at high V.

ATLAS = 2048

ZONES = {
    #  name     rows (top, bottom)   columns   -> cell size          aspect
    "hair": {"rows": (0, 1280), "columns": 16},      # 128 x 1280  ->  10.0
    "lash": {"rows": (1280, 1664), "columns": 32},   #  64 x  384  ->   6.0
    "brow": {"rows": (1664, 2048), "columns": 4},    # 512 x  384  ->   0.75
}


def zone_geometry(name: str) -> dict:
    zone = ZONES[name]
    top, bottom = zone["rows"]
    columns = zone["columns"]
    cell_width = ATLAS // columns
    return {
        "name": name,
        "rows": (top, bottom),
        "columns": columns,
        "cell_width": cell_width,
        "cell_height": bottom - top,
        "aspect": (bottom - top) / cell_width,
        # UV: image row 0 is V = 1.0, so a row range maps to V descending.
        "v_low": 1.0 - bottom / ATLAS,
        "v_high": 1.0 - top / ATLAS,
    }


ALL_ZONES = {name: zone_geometry(name) for name in ZONES}
