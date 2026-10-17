"""Illustrative field layout for the demo farm (the organisers' parcel shapes are scattered squares).

Creates app/assets/farm_layout.json: 30 fields of the demo farm (all 21 winter-cereal parcels + the 9 largest others)
placed in a rural landscape (blocks between roads, field tracks, woodland, stream, farmstead, village). Field SIZES on
the map are illustrative (the real parcels are all 5-9 ha, which looks unlike a real farm); areas, soils, crops and
every status shown on hover and in the tables come from the data and the engine.
Run once:  python tools/make_farm_layout.py   (needs FIELDGO_DATA_DIR and `pip install squarify`)
"""
import json
import math
from pathlib import Path

import numpy as np
import squarify

from engine import data

OUT = Path(__file__).resolve().parents[1] / "app" / "assets" / "farm_layout.json"
ROT = math.radians(-9)                          # slight rotation: fields rarely face north exactly
INSET = 7.0                                     # m of headland / track between fields


def rot(x, y, cx=1300, cy=850):
    dx, dy = x - cx, y - cy
    return cx + dx * math.cos(ROT) - dy * math.sin(ROT), cy + dx * math.sin(ROT) + dy * math.cos(ROT)


RNG = np.random.default_rng(13525)
SIZE_FACTORS = [2.6, 0.5, 1.4, 0.8, 3.1, 0.45, 1.1, 1.9, 0.6, 1.0]   # varied, deterministic


def poly_rect(x, y, w, h):
    j = lambda: RNG.uniform(-10, 10)  # noqa: E731  (slightly irregular corners)
    pts = [(x + INSET + j(), y + INSET + j()), (x + w - INSET + j(), y + INSET + j()),
           (x + w - INSET + j(), y + h - INSET + j()), (x + INSET + j(), y + h - INSET + j())]
    pts = [rot(px, py) for px, py in pts]
    return [round(p[0], 1) for p in pts + pts[:1]], [round(p[1], 1) for p in pts + pts[:1]]


def main():
    farm = data.load_farm("FARM-13525")
    autumn = farm[farm.crop.isin(["BARL", "COWT", "RAPE"])]
    others = farm[~farm.crop.isin(["BARL", "COWT", "RAPE"])].nlargest(9, "area_ha")
    sel = autumn.sort_values("parcel_id")
    west, east = sel.iloc[::3], sel.drop(sel.index[::3])            # spread barley/wheat over two blocks
    blocks = [  # (x, y, w, h) in m, parcels
        ((300, 930, 1100, 760), west),
        ((1480, 930, 1080, 480), east),
        ((300, 170, 2300, 640), others),
    ]
    fields = []
    for (bx, by, bw, bh), parcels in blocks:
        parcels = parcels.sort_values("area_ha", ascending=False)
        vis = [a * SIZE_FACTORS[i % len(SIZE_FACTORS)] for i, a in enumerate(parcels.area_ha)]
        order = np.argsort(vis)[::-1]
        parcels, vis = parcels.iloc[order], [vis[i] for i in order]
        sizes = squarify.normalize_sizes(vis, bw, bh)
        rects = squarify.squarify(sizes, bx, by, bw, bh)
        for r, p in zip(rects, parcels.itertuples()):
            xs, ys = poly_rect(r["x"], r["y"], r["dx"], r["dy"])
            fields.append({"parcel_id": p.parcel_id, "xs": xs, "ys": ys})
    t = np.linspace(0, 2600, 60)
    road = [rot(x, 870 + 25 * math.sin(x / 380)) for x in t]
    track = [rot(1440, y) for y in np.linspace(880, 1720, 10)]
    stream = [rot(x, 60 + 30 * math.sin(x / 260)) for x in np.linspace(0, 2750, 60)]
    wood = [rot(x, y) for x, y in [(1500, 1440), (2560, 1430), (2640, 1760), (1560, 1780), (1480, 1600), (1500, 1440)]]
    lane = [rot(x, y) for x, y in [(175, 880), (175, 940)]]
    yard = [rot(x, y) for x, y in [(120, 930), (230, 930), (230, 1060), (120, 1060), (120, 930)]]
    village = [rot(x, y) for x, y in [(30, 1150), (230, 1180), (240, 1700), (20, 1700), (30, 1150)]]
    sp = lambda pts: {"xs": [round(p[0], 1) for p in pts], "ys": [round(p[1], 1) for p in pts]}  # noqa: E731
    OUT.write_text(json.dumps({"note": "Illustrative layout; field sizes on the map are illustrative.",
                               "fields": fields, "road": sp(road), "track": sp(track), "stream": sp(stream),
                               "wood": sp(wood), "lane": sp(lane), "farmyard": sp(yard), "village": sp(village)}))
    print(len(fields), "fields ->", OUT)


if __name__ == "__main__":
    main()
