"""Static PNG of the farm map for the deck: python tools/render_farm_map.py [YYYY-MM-DD] [machine].

Real orthophoto (GUGiK) at full resolution, traced outlines coloured by the engine's status on that day.
"""
import json
import sys
from pathlib import Path

import pandas as pd
from PIL import Image, ImageDraw, ImageFont

from engine import data, soil, status

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "app" / "assets"
RGB = {"GO": (26, 152, 80), "CAUTION": (245, 166, 35), "NO-GO": (215, 48, 39), "not available": (158, 158, 158)}
CROP = {"BARL": "barley", "COWT": "wheat", "RAPE": "rapeseed", "MAIZ": "maize", "SUNF": "sunflower", "HAY": "grass"}


def font(size, bold=False):
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    try:
        return ImageFont.truetype(name, size)
    except OSError:
        return ImageFont.load_default()


def main(date="2016-10-11", machine="M2", out=ASSETS / "farm_map_demo.png", image=None):
    date = pd.Timestamp(date)
    f = data.load_farm("FARM-13525")
    sw = soil.soil_water(f, data.load_weather(f.nuts3.iloc[0]))
    lc, _ = status.axle_load_class(machine, 100)
    st_ = status.status_table(sw[sw.date == date], f, lc)
    stat = dict(zip(st_.parcel_id, st_.status))
    info = f.set_index("parcel_id")
    lay = json.loads((ASSETS / "farm_layout.json").read_text())
    base = Image.open(image) if image else Image.open(ASSETS / lay["image"])
    k = base.width / lay["width"]
    base = base.convert("RGBA")
    over = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(over)
    counts = {}
    for fld in lay["fields"]:
        s = stat.get(fld["parcel_id"], "not available")
        counts[s] = counts.get(s, 0) + 1
        pts = [(x * k, y * k) for x, y in zip(fld["xs"], fld["ys"])]
        d.polygon(pts, fill=RGB[s] + (100,))
        d.line(pts, fill=RGB[s] + (255,), width=int(3 * k), joint="curve")
    img = Image.alpha_composite(base, over)
    d = ImageDraw.Draw(img)
    for fld in lay["fields"]:
        r = info.loc[fld["parcel_id"]]
        xs, ys = fld["xs"][:-1], fld["ys"][:-1]
        cx, cy = sum(xs) / len(xs) * k, sum(ys) / len(ys) * k
        t1, t2 = fld["parcel_id"][-3:], CROP.get(r.crop, r.crop)
        f1, f2 = font(int(13 * k), True), font(int(10 * k))
        w = max(d.textlength(t1, font=f1), d.textlength(t2, font=f2)) + 10 * k
        d.rounded_rectangle([cx - w / 2, cy - 15 * k, cx + w / 2, cy + 15 * k], radius=5 * k, fill=(0, 0, 0, 150))
        d.text((cx, cy - 6 * k), t1, font=f1, fill="white", anchor="mm")
        d.text((cx, cy + 8 * k), t2, font=f2, fill=(235, 235, 235), anchor="mm")
    # title, legend, scale, attribution
    d.rounded_rectangle([12 * k, 12 * k, 610 * k, 74 * k], radius=8 * k, fill=(255, 255, 255, 225))
    d.text((24 * k, 20 * k), f"FieldGo · field status on {date:%d %b %Y}", font=font(int(19 * k), True), fill=(30, 30, 30))
    x = 24 * k
    for s in ("GO", "CAUTION", "NO-GO"):
        d.rectangle([x, 50 * k, x + 14 * k, 64 * k], fill=RGB[s])
        lbl = f"{s}  {counts.get(s, 0)} fields"
        d.text((x + 20 * k, 57 * k), lbl, font=font(int(13 * k)), fill=(30, 30, 30), anchor="lm")
        x += d.textlength(lbl, font=font(int(13 * k))) + 44 * k
    d.text((x, 57 * k), f"tractor + drill ({machine})", font=font(int(12 * k)), fill=(90, 90, 90), anchor="lm")
    h = img.height
    d.line([(30 * k, h - 30 * k), (230 * k, h - 30 * k)], fill="white", width=int(3 * k))
    d.text((130 * k, h - 38 * k), "500 m", font=font(int(12 * k), True), fill="white", anchor="mb")
    note = lay["attribution"] + " · outlines traced from the image; illustrative location · statuses: FieldGo engine"
    tw = d.textlength(note, font=font(int(10 * k)))
    d.rectangle([img.width - tw - 16 * k, h - 22 * k, img.width, h], fill=(0, 0, 0, 140))
    d.text((img.width - 8 * k, h - 11 * k), note, font=font(int(10 * k)), fill="white", anchor="rm")
    img.convert("RGB").save(out, quality=90)
    print(counts, "->", out)


if __name__ == "__main__":
    main(*sys.argv[1:3], **({"image": sys.argv[3]} if len(sys.argv) > 3 else {}))
