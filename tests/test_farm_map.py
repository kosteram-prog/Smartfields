"""Farm trafficability map: statuses and field geometries (no FIELDGO_DATA_DIR needed)."""
import datetime as dt
import sys
from pathlib import Path

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


def test_bundled_osm_rings_rural_and_closed():
    farm = stubs.load_farm()
    rings, source = farm_map.parcel_rings(farm)
    assert "OSM" in source or "shape_wkt" in source
    assert len(rings) == len(farm)
    for ring in rings.values():
        assert len(ring) >= 4
        assert ring[0] == ring[-1]
        assert farm_map._looks_geographic(ring)
    # Must sit in rural PL415 countryside, not Poznań city centre (~52.41, 16.93)
    lats = [p[1] for ring in rings.values() for p in ring]
    lons = [p[0] for ring in rings.values() for p in ring]
    assert 52.20 < sum(lats) / len(lats) < 52.35
    assert 16.55 < sum(lons) / len(lons) < 16.85
    assert max(lats) < 52.38  # south of city core


def test_geographic_wkt_on_frame_preferred():
    farm = stubs.load_farm().head(1).copy()
    farm["shape_wkt"] = ['POLYGON((16.9 52.4, 16.91 52.4, 16.91 52.41, 16.9 52.41, 16.9 52.4))']
    rings, source = farm_map.parcel_rings(farm)
    assert "shape_wkt" in source
    ring = rings[str(farm.parcel_id.iloc[0])]
    assert abs(ring[0][0] - 16.9) < 1e-9
    assert abs(ring[0][1] - 52.4) < 1e-9
