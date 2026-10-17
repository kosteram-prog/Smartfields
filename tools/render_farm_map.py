"""Static PNG of the illustrative farm map for the deck: python tools/render_farm_map.py [YYYY-MM-DD] [machine]."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from components import farm_map  # noqa: E402
from engine import data, soil, status  # noqa: E402

date = pd.Timestamp(sys.argv[1] if len(sys.argv) > 1 else "2016-10-13")
machine = sys.argv[2] if len(sys.argv) > 2 else "M2"
f = data.load_farm("FARM-13525")
sw = soil.soil_water(f, data.load_weather(f.nuts3.iloc[0]))
lc, _ = status.axle_load_class(machine, 100)
st_ = status.status_table(sw[sw.date == date], f, lc)
f["status"] = f.parcel_id.map(dict(zip(st_.parcel_id, st_.status))).fillna("not available")
fig = farm_map.figure(f, height=760, title=f"FieldGo · field status on {date:%d %b %Y} · tractor + drill ({machine})")
out = Path(__file__).resolve().parents[1] / "app" / "assets"
html = out / "farm_map_demo.html"
fig.write_html(html, include_plotlyjs="cdn" if False else True, config={"displayModeBar": False})
from playwright.sync_api import sync_playwright  # noqa: E402
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1400, "height": 780}, device_scale_factor=2)
    pg.goto(html.as_uri()); pg.wait_for_timeout(1500)
    pg.screenshot(path=str(out / "farm_map_demo.png"), full_page=True)
    b.close()
html.unlink()
print(f.status.value_counts().to_dict(), "->", out / "farm_map_demo.png")
