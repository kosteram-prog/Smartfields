"""Farm map on a real orthophoto (Geoportal, GUGiK; open data) with field outlines traced from it.

Creates app/assets/farm_ortho.jpg and app/assets/farm_layout.json. The image shows a real rural area of
Wielkopolska (the demo region); the 30 outlines were traced from the image (Felzenszwalb segmentation of the
orthophoto, segments picked by hand, 4 drawn by hand) and are stored in tools/farm_fields_px.json (pixels of the
1600 x 1040 image, 2.5 m per pixel). Which parcel of the synthetic demo farm is drawn on which field is illustrative:
greener fields (emerged autumn crops) carry the 21 winter-cereal parcels, the others the 9 largest remaining parcels.
Every status, crop, area and soil on the map comes from the data and the engine. This is NOT the farm's real location.

Run once:  python tools/make_farm_layout.py   (needs network to geoportal.gov.pl, FIELDGO_DATA_DIR)
"""
import io
import json
import math
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from engine import data

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "app" / "assets"
WMS = ("https://mapy.geoportal.gov.pl/wss/service/PZGIK/ORTO/WMS/HighResolution?SERVICE=WMS&VERSION=1.3.0"
       "&REQUEST=GetMap&LAYERS=Raster&STYLES=&CRS=EPSG:3857&FORMAT=image/jpeg&WIDTH=3200&HEIGHT=2080&BBOX={}")
CENTRE, HALF_M = (52.05, 16.75), (2000, 1300)          # ~4 x 2.6 km
W, H = 1600, 1040


def fetch() -> Image.Image:
    lat, lon = CENTRE
    r = 6378137
    x, y = r * math.radians(lon), r * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))
    k = 1 / math.cos(math.radians(lat))
    bbox = f"{x - HALF_M[0] * k},{y - HALF_M[1] * k},{x + HALF_M[0] * k},{y + HALF_M[1] * k}"
    with urllib.request.urlopen(WMS.format(bbox), timeout=60) as resp:
        return Image.open(io.BytesIO(resp.read())).convert("RGB")


def greenness(img: np.ndarray, poly) -> float:
    m = Image.new("L", (W, H), 0)
    ImageDraw.Draw(m).polygon([tuple(p) for p in poly], fill=1)
    px = img[np.asarray(m, bool)].astype(float)
    return float((px[:, 1] - px[:, 0]).mean())


def area_px(poly) -> float:
    x, y = np.asarray(poly).T
    return 0.5 * abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))


def main():
    img = fetch().resize((W, H), Image.LANCZOS)
    img.save(ASSETS / "farm_ortho.jpg", quality=82)
    arr = np.asarray(img)
    polys = [[[min(max(x, 0), W), min(max(y, 0), H)] for x, y in p]
             for p in json.loads((ROOT / "tools" / "farm_fields_px.json").read_text()).values()]
    farm = data.load_farm("FARM-13525")
    autumn = farm[farm.crop.isin(["BARL", "COWT", "RAPE"])].sort_values("area_ha", ascending=False)
    others = farm[~farm.crop.isin(["BARL", "COWT", "RAPE"])].nlargest(9, "area_ha")
    by_green = sorted(polys, key=lambda p: -greenness(arr, p))
    green, bare = by_green[:len(autumn)], by_green[len(autumn):]
    fields = []
    for group, parcels in ((green, autumn), (bare, others)):
        for poly, pid in zip(sorted(group, key=lambda p: -area_px(p)), parcels.parcel_id):
            fields.append({"parcel_id": pid, "xs": [p[0] for p in poly] + [poly[0][0]],
                           "ys": [p[1] for p in poly] + [poly[0][1]]})
    (ASSETS / "farm_layout.json").write_text(json.dumps({
        "image": "farm_ortho.jpg", "width": W, "height": H, "m_per_px": 2.5,
        "attribution": "Orthophoto: GUGiK (geoportal.gov.pl), open data",
        "note": "Real orthophoto of a rural area in Wielkopolska; outlines traced from it. Illustrative location: "
                "not the demo farm's real fields. Status, crop, area and soil come from the data and the engine.",
        "fields": fields}))
    print(len(fields), "fields")


if __name__ == "__main__":
    main()
