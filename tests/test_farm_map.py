"""Farm map on a real orthophoto: 30 traced fields, all real parcels of the demo farm, closed polygons."""
import json
from pathlib import Path

import pytest

LAYOUT = Path(__file__).resolve().parents[1] / "app" / "assets" / "farm_layout.json"


def test_demo_picture_is_shipped():
    assert (LAYOUT.parent / "farm_map_demo.jpg").is_file()


def test_layout_has_30_closed_fields():
    lay = json.loads(LAYOUT.read_text())
    assert len(lay["fields"]) == 30
    assert len({f["parcel_id"] for f in lay["fields"]}) == 30
    for f in lay["fields"]:
        assert f["xs"][0] == f["xs"][-1] and f["ys"][0] == f["ys"][-1]
    assert (LAYOUT.parent / lay["image"]).exists()
    assert "GUGiK" in lay["attribution"]
    for f in lay["fields"]:
        assert all(0 <= x <= lay["width"] for x in f["xs"]) and all(0 <= y <= lay["height"] for y in f["ys"])


@pytest.mark.needs_data
def test_layout_parcels_exist_and_cover_all_autumn():
    from engine import data
    farm = data.load_farm("FARM-13525")
    ids = {f["parcel_id"] for f in json.loads(LAYOUT.read_text())["fields"]}
    assert ids <= set(farm.parcel_id)
    assert set(farm[farm.crop.isin(["BARL", "COWT", "RAPE"])].parcel_id) <= ids


def test_figure_builds_with_statuses():
    import sys
    import pandas as pd
    sys.path.insert(0, str(LAYOUT.parents[1]))
    from components import farm_map
    ids = [f["parcel_id"] for f in farm_map.layout()["fields"]]
    farm = pd.DataFrame({"parcel_id": ids, "crop": "BARL", "area_ha": 6.0, "status": "GO"})
    fig = farm_map.figure(farm, selected=ids[0])
    assert sum(1 for t in fig.data if t.fill == "toself") >= 30
    chosen = next(t for t in fig.data if t.fill == "toself" and "selected" in (t.text or ""))
    assert chosen.line.width == 5


def test_plot_zones_cover_every_plot_and_are_ordered():
    """Within-plot zones (tools/make_plot_zones.py): wettest third has the biggest radar rise, lower NDVI zone is lowest."""
    import numpy as np
    meta = json.loads((LAYOUT.parent / "plot_zones.json").read_text())
    grids = np.load(LAYOUT.parent / "plot_zones.npz")
    ids = {f["parcel_id"] for f in json.loads(LAYOUT.read_text())["fields"]}
    assert set(meta["plots"]) == ids
    for pid, s in meta["plots"].items():
        w = grids[pid + "|wet"]
        assert set(np.unique(w)) <= {-1, 0, 1, 2} and (w >= 0).sum() > 20
        assert s["wet_zone_change_db"][0] > s["wet_zone_change_db"][1] > s["wet_zone_change_db"][2]
        if s.get("ndvi_zone_rel"):
            assert s["ndvi_zone_rel"][0] < s["ndvi_zone_rel"][1] < s["ndvi_zone_rel"][2]
