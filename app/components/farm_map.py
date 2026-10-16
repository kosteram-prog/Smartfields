"""Farm trafficability map: parcel outlines coloured GO / CAUTION / NO-GO (field access)."""
from __future__ import annotations

import math
import re

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import config
import ui
from engine import params as prm

# Poznan region (PL415) anchor for synthetic stub polygons
_ORIGIN_LAT, _ORIGIN_LON = 52.406, 16.925
_M_PER_DEG_LAT = 111_320.0

# Semi-transparent fills; strokes use solid STATUS_COLORS
_FILL = {
    "GO": "rgba(26, 152, 80, 0.55)",
    "CAUTION": "rgba(245, 166, 35, 0.55)",
    "NO-GO": "rgba(215, 48, 39, 0.55)",
    "not available": "rgba(158, 158, 158, 0.45)",
}


def _m_per_deg_lon(lat: float) -> float:
    return _M_PER_DEG_LAT * math.cos(math.radians(lat))


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


def _synthetic_ring(parcel_id: str, area_ha: float, index: int) -> list[tuple[float, float]]:
    """Deterministic irregular polygon near Poznan, sized roughly by area_ha."""
    side_m = max(80.0, math.sqrt(max(area_ha, 0.5) * 10_000))
    col, row = index % 3, index // 3
    gap = side_m * 1.35
    cx_m = col * gap
    cy_m = -row * gap
    # slight hash offset so parcels don't look like a perfect grid
    h = sum(ord(c) for c in parcel_id) % 17
    cx_m += (h - 8) * 12
    cy_m += (h % 5 - 2) * 18
    # 5-vertex outline (closed)
    offsets = [
        (-0.55, -0.40), (0.50, -0.48), (0.58, 0.35), (0.05, 0.55), (-0.52, 0.28), (-0.55, -0.40),
    ]
    lon_scale = 1.0 / _m_per_deg_lon(_ORIGIN_LAT)
    lat_scale = 1.0 / _M_PER_DEG_LAT
    return [
        (_ORIGIN_LON + (cx_m + ox * side_m) * lon_scale,
         _ORIGIN_LAT + (cy_m + oy * side_m) * lat_scale)
        for ox, oy in offsets
    ]


def parcel_rings(farm: pd.DataFrame) -> dict[str, list[tuple[float, float]]]:
    """Map parcel_id -> closed (lon, lat) ring. Prefer geographic shape_wkt when present."""
    rings: dict[str, list[tuple[float, float]]] = {}
    has_wkt = "shape_wkt" in farm.columns
    for i, r in enumerate(farm.itertuples()):
        ring = None
        if has_wkt:
            parsed = _parse_wkt_polygon(getattr(r, "shape_wkt", None))
            if parsed and _looks_geographic(parsed):
                ring = parsed
        if ring is None:
            ring = _synthetic_ring(r.parcel_id, float(r.area_ha), i)
        rings[r.parcel_id] = ring
    return rings


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

    # Prefer real soil-water when FIELDGO_DATA_DIR is set; otherwise stub tables.
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


def _figure(farm: pd.DataFrame, statuses: pd.DataFrame, rings: dict[str, list[tuple[float, float]]],
            date) -> go.Figure:
    status_of = dict(zip(statuses.parcel_id, statuses.status))
    crop_of = dict(zip(farm.parcel_id, farm.crop)) if "crop" in farm.columns else {}
    area_of = dict(zip(farm.parcel_id, farm.area_ha))
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
            line=dict(width=2, color=ui.STATUS_COLORS.get(status, ui.STATUS_COLORS["not available"])),
            name=pid,
            hovertemplate=hover + "<extra></extra>",
            showlegend=False,
        ))

    if all_lats and all_lons:
        center = dict(lat=sum(all_lats) / len(all_lats), lon=sum(all_lons) / len(all_lons))
        span = max(max(all_lats) - min(all_lats), max(all_lons) - min(all_lons), 0.002)
        zoom = 12 if span < 0.03 else 11 if span < 0.08 else 10
    else:
        center = dict(lat=_ORIGIN_LAT, lon=_ORIGIN_LON)
        zoom = 12

    fig.update_layout(
        map=dict(style="open-street-map", center=center, zoom=zoom),
        margin=dict(l=0, r=0, t=0, b=0),
        height=480,
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
    rings = parcel_rings(farm)
    stub = bool(statuses["stub"].any()) if len(statuses) else True
    has_geo_wkt = False
    if "shape_wkt" in farm.columns:
        for wkt in farm["shape_wkt"].dropna():
            parsed = _parse_wkt_polygon(str(wkt))
            if parsed and _looks_geographic(parsed):
                has_geo_wkt = True
                break
    geom_note = ("parcel polygons from shape_wkt" if has_geo_wkt
                 else "synthetic parcel outlines near PL415 (Poznan)")

    st.subheader("Trafficability map")
    st.caption(
        f"Field access for {pd.Timestamp(date):%d %b %Y} · {machine_id} at {load_pct:g}% load · "
        f"{geom_note}. Colours = przejazność (GO / CAUTION / NO-GO)."
    )
    _legend()
    st.plotly_chart(_figure(farm, statuses, rings, date), use_container_width=True)
    ui.show_origin("modelled+synthetic", stub=stub)
    counts = statuses.status.value_counts()
    bits = [f"{s}: {int(counts.get(s, 0))}" for s in ("GO", "CAUTION", "NO-GO") if s in counts.index]
    if bits:
        st.caption("Parcels on map — " + " · ".join(bits))
    return statuses
