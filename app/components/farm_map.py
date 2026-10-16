"""Farm trafficability map: real field outlines coloured GO / CAUTION / NO-GO (field access)."""
from __future__ import annotations

import json
import math
import re
from functools import lru_cache
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import config
import ui
from engine import params as prm

# Bundled rural field outlines (OSM farmland, PL415 countryside) for stub / no-WKT mode
_ASSET_GEOJSON = Path(__file__).resolve().parents[1] / "assets" / "farm_13525_parcels.geojson"

# Semi-transparent fills; strokes use solid STATUS_COLORS
_FILL = {
    "GO": "rgba(26, 152, 80, 0.55)",
    "CAUTION": "rgba(245, 166, 35, 0.55)",
    "NO-GO": "rgba(215, 48, 39, 0.55)",
    "not available": "rgba(158, 158, 158, 0.45)",
}

# Esri World Imagery — rural fields read clearly (no Mapbox token)
_SATELLITE_TILES = [
    "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
]


def _parse_wkt_polygon(wkt: str) -> list[tuple[float, float]] | None:
    """Parse a simple POLYGON((x y, ...)) WKT into (lon, lat) rings. No shapely dependency."""
    if not isinstance(wkt, str) or "POLYGON" not in wkt.upper():
        return None
    m = re.search(r"POLYGON\s*\(\((.+?)\)\)", wkt, flags=re.IGNORECASE | re.DOTALL)
    if not m:
        return None
    pts: list[tuple[float, float]] = []
    for pair in m.group(1).split(","):
        parts = pair.strip().split()
        if len(parts) < 2:
            continue
        x, y = float(parts[0]), float(parts[1])
        pts.append((x, y))
    if len(pts) < 3:
        return None
    if pts[0] != pts[-1]:
        pts.append(pts[0])
    return pts


def _looks_geographic(ring: list[tuple[float, float]]) -> bool:
    xs, ys = [p[0] for p in ring], [p[1] for p in ring]
    return all(-180 <= x <= 180 for x in xs) and all(-90 <= y <= 90 for y in ys)


@lru_cache(maxsize=1)
def _bundled_rings() -> dict[str, list[tuple[float, float]]]:
    """Real OSM farmland polygons shipped in app/assets (rural PL415)."""
    if not _ASSET_GEOJSON.is_file():
        return {}
    geo = json.loads(_ASSET_GEOJSON.read_text())
    out: dict[str, list[tuple[float, float]]] = {}
    for feat in geo.get("features", []):
        pid = feat.get("properties", {}).get("parcel_id")
        geom = feat.get("geometry") or {}
        if not pid or geom.get("type") != "Polygon":
            continue
        coords = geom["coordinates"][0]
        ring = [(float(x), float(y)) for x, y in coords]
        if ring and ring[0] != ring[-1]:
            ring.append(ring[0])
        if _looks_geographic(ring):
            out[str(pid)] = ring
    return out


def _wkt_from_data_dir(farm: pd.DataFrame) -> dict[str, list[tuple[float, float]]]:
    """Load geographic shape_wkt from FIELDGO_DATA_DIR parcels.parquet when present."""
    data_dir = config.data_dir_or_none()
    if data_dir is None:
        return {}
    path = data_dir / "parcels.parquet"
    if not path.is_file():
        return {}
    try:
        raw = pd.read_parquet(path)
    except Exception:
        return {}
    if "shape_wkt" not in raw.columns or "parcel_id" not in raw.columns:
        return {}
    ids = set(farm.parcel_id.astype(str))
    out: dict[str, list[tuple[float, float]]] = {}
    for r in raw[raw.parcel_id.astype(str).isin(ids)].itertuples():
        ring = _parse_wkt_polygon(getattr(r, "shape_wkt", None))
        if ring and _looks_geographic(ring):
            out[str(r.parcel_id)] = ring
    return out


def parcel_rings(farm: pd.DataFrame) -> tuple[dict[str, list[tuple[float, float]]], str]:
    """Return (parcel_id -> closed lon/lat ring, geometry source label).

    Preference order:
    1. Geographic shape_wkt already on the farm frame
    2. Geographic shape_wkt from FIELDGO_DATA_DIR/parcels.parquet
    3. Bundled OSM farmland GeoJSON (rural PL415, area-matched to demo parcels)
    """
    rings: dict[str, list[tuple[float, float]]] = {}
    source = "none"

    if "shape_wkt" in farm.columns:
        for r in farm.itertuples():
            parsed = _parse_wkt_polygon(getattr(r, "shape_wkt", None))
            if parsed and _looks_geographic(parsed):
                rings[str(r.parcel_id)] = parsed
        if rings:
            return rings, "organisers' shape_wkt (on farm frame)"

    from_dir = _wkt_from_data_dir(farm)
    if from_dir:
        return from_dir, f"organisers' shape_wkt ({config.ENV_VAR}/parcels.parquet)"

    bundled = _bundled_rings()
    for pid in farm.parcel_id.astype(str):
        if pid in bundled:
            rings[pid] = bundled[pid]
    if rings:
        return rings, "OSM farmland boundaries (bundled GeoJSON, rural PL415)"

    return {}, "no geometries available"


def _status_fns():
    """Same resolve path as engine.today: real engine.status if present, else stubs."""
    try:
        from engine import status as st_mod
        if hasattr(st_mod, "classify_day") and hasattr(st_mod, "axle_load_class"):
            return st_mod.classify_day, st_mod.axle_load_class, False
    except ImportError:
        pass
    from engine import stubs
    return stubs.classify_day, stubs.axle_load_class, True


def trafficability_table(farm: pd.DataFrame, date, machine_id: str = "M2",
                         load_pct: float = 100, passes: int = 1,
                         operation: str = "sowing") -> pd.DataFrame:
    """Per-parcel field-access status for the replay date (GO / CAUTION / NO-GO)."""
    classify_day, axle_load_class, status_is_stub = _status_fns()
    load_class, _ = axle_load_class(machine_id, load_pct)

    is_stub = True
    if config.data_dir_or_none() is not None:
        try:
            from engine import data, soil
            holding = (farm["holding_id"].iloc[0] if "holding_id" in farm.columns
                       else prm.DEMO["holding_id"].value)
            nuts3 = farm["nuts3"].iloc[0] if "nuts3" in farm.columns else prm.DEMO["nuts3"].value
            full = data.load_farm(holding)
            wx = data.load_weather(nuts3)
            sw = soil.soil_water(full, wx)
            is_stub = status_is_stub
        except Exception:
            from engine import stubs
            sw = stubs.soil_water(farm)
    else:
        from engine import stubs
        sw = stubs.soil_water(farm)

    d = pd.Timestamp(date).normalize()
    day = sw[pd.to_datetime(sw["date"]).dt.normalize() == d]
    by_id = {r.parcel_id: r for r in day.itertuples()}
    tex = farm.set_index("parcel_id")

    rows = []
    for pid in farm.parcel_id:
        p = tex.loc[pid]
        hit = by_id.get(pid)
        if hit is None:
            status = "not available"
        else:
            res = classify_day(float(hit.RWC_eff), float(p.clay_pct), float(p.sand_pct),
                               float(hit.rain_today_mm), float(hit.rain_prev24h_mm), float(hit.tmax_c),
                               load_class, int(passes), operation)
            status = res["access"]
        rows.append({"parcel_id": pid, "status": status, "origin": "modelled", "stub": is_stub})
    return pd.DataFrame(rows)


def _fit_zoom(lat_span: float, lon_span: float, lat0: float) -> float:
    """Rough zoom so parcels fill the view (rural fields, not city overview)."""
    span_deg = max(lat_span, lon_span * math.cos(math.radians(lat0)), 1e-4)
    # ~0.01 deg ≈ zoom 13-14; ~0.05 ≈ 12; ~0.1 ≈ 11
    if span_deg < 0.008:
        return 14.5
    if span_deg < 0.02:
        return 13.5
    if span_deg < 0.05:
        return 12.5
    if span_deg < 0.1:
        return 11.5
    return 10.5


def _figure(farm: pd.DataFrame, statuses: pd.DataFrame, rings: dict[str, list[tuple[float, float]]],
            date) -> go.Figure:
    status_of = dict(zip(statuses.parcel_id.astype(str), statuses.status))
    crop_of = dict(zip(farm.parcel_id.astype(str), farm.crop)) if "crop" in farm.columns else {}
    area_of = dict(zip(farm.parcel_id.astype(str), farm.area_ha))
    fig = go.Figure()
    all_lats: list[float] = []
    all_lons: list[float] = []

    for pid, ring in rings.items():
        status = status_of.get(pid, "not available")
        lons = [p[0] for p in ring]
        lats = [p[1] for p in ring]
        all_lons.extend(lons)
        all_lats.extend(lats)
        crop = crop_of.get(pid, "")
        area = area_of.get(pid, float("nan"))
        hover = (f"<b>{pid}</b><br>Access: {status}<br>"
                 f"{crop} · {area:.1f} ha<br>{pd.Timestamp(date):%d %b %Y}")
        fig.add_trace(go.Scattermap(
            lon=lons, lat=lats, mode="lines",
            fill="toself",
            fillcolor=_FILL.get(status, _FILL["not available"]),
            line=dict(width=2.5, color=ui.STATUS_COLORS.get(status, ui.STATUS_COLORS["not available"])),
            name=pid,
            hovertemplate=hover + "<extra></extra>",
            showlegend=False,
        ))

    if all_lats and all_lons:
        lat0 = (min(all_lats) + max(all_lats)) / 2
        lon0 = (min(all_lons) + max(all_lons)) / 2
        # pad slightly so edges are not clipped
        pad_lat = max((max(all_lats) - min(all_lats)) * 0.15, 0.002)
        pad_lon = max((max(all_lons) - min(all_lons)) * 0.15, 0.002)
        center = dict(lat=lat0, lon=lon0)
        zoom = _fit_zoom(max(all_lats) - min(all_lats) + 2 * pad_lat,
                         max(all_lons) - min(all_lons) + 2 * pad_lon, lat0)
    else:
        center = dict(lat=52.27, lon=16.70)
        zoom = 13

    fig.update_layout(
        map=dict(
            style="white-bg",
            center=center,
            zoom=zoom,
            layers=[dict(
                below="traces",
                sourcetype="raster",
                type="raster",
                source=_SATELLITE_TILES,
                sourceattribution="Tiles © Esri — Source: Esri, Maxar, Earthstar Geographics",
            )],
        ),
        margin=dict(l=0, r=0, t=0, b=0),
        height=520,
        uirevision="farm-trafficability",
    )
    return fig


def _legend() -> None:
    items = [
        ("GO", "can drive / przejezdne"),
        ("CAUTION", "caution / ostrożnie"),
        ("NO-GO", "cannot drive / nieprzejezdne"),
    ]
    pills = "".join(
        f"<span style='display:inline-flex;align-items:center;margin-right:18px'>"
        f"<span style='width:14px;height:14px;border-radius:3px;background:{ui.STATUS_COLORS[s]};"
        f"display:inline-block;margin-right:6px;border:1px solid #3333'></span>"
        f"<small><b>{s}</b> — {label}</small></span>"
        for s, label in items
    )
    st.markdown(pills, unsafe_allow_html=True)


def render(farm: pd.DataFrame, date, machine_id: str = "M2",
           load_pct: float = 100, passes: int = 1) -> pd.DataFrame:
    """Draw the trafficability map and return the per-parcel status table."""
    statuses = trafficability_table(farm, date, machine_id=machine_id, load_pct=load_pct, passes=passes)
    rings, geom_source = parcel_rings(farm)
    stub = bool(statuses["stub"].any()) if len(statuses) else True

    st.subheader("Trafficability map")
    st.caption(
        f"Field access for {pd.Timestamp(date):%d %b %Y} · {machine_id} at {load_pct:g}% load · "
        f"basemap: satellite imagery · geometries: {geom_source}. "
        f"Colours = przejazność (GO / CAUTION / NO-GO)."
    )
    _legend()
    if not rings:
        st.warning("No parcel geometries available to plot.")
    else:
        st.plotly_chart(_figure(farm, statuses, rings, date), use_container_width=True)
    ui.show_origin("modelled+synthetic", stub=stub)
    counts = statuses.status.value_counts()
    bits = [f"{s}: {int(counts.get(s, 0))}" for s in ("GO", "CAUTION", "NO-GO") if s in counts.index]
    if bits:
        st.caption("Parcels on map — " + " · ".join(bits))
    return statuses
