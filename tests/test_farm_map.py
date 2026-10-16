"""Farm trafficability map: statuses and synthetic geometries (no FIELDGO_DATA_DIR needed)."""
import datetime as dt
import sys
from pathlib import Path

import pandas as pd

APP = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))

from components import farm_map  # noqa: E402
from engine import stubs  # noqa: E402


def test_trafficability_table_stub_demo_date():
    farm = stubs.load_farm()
    out = farm_map.trafficability_table(farm, dt.date(2016, 10, 13))
    assert set(out.parcel_id) == set(farm.parcel_id)
    assert set(out.status).issubset({"GO", "CAUTION", "NO-GO", "not available"})
    assert out.loc[out.parcel_id == "PARCEL-0149906", "status"].item() == "GO"
    assert out.loc[out.parcel_id == "PARCEL-0149869", "status"].item() == "CAUTION"


def test_parcel_rings_closed_and_geographic():
    farm = stubs.load_farm()
    rings = farm_map.parcel_rings(farm)
    assert len(rings) == len(farm)
    for ring in rings.values():
        assert len(ring) >= 4
        assert ring[0] == ring[-1]
        assert farm_map._looks_geographic(ring)


def test_geographic_wkt_preferred():
    farm = stubs.load_farm().head(1).copy()
    farm["shape_wkt"] = ['POLYGON((16.9 52.4, 16.91 52.4, 16.91 52.41, 16.9 52.41, 16.9 52.4))']
    rings = farm_map.parcel_rings(farm)
    ring = rings[farm.parcel_id.iloc[0]]
    assert abs(ring[0][0] - 16.9) < 1e-9
    assert abs(ring[0][1] - 52.4) < 1e-9
