"""Farm map: real orthophoto (Geoportal, GUGiK) with field outlines traced from it, coloured by the engine's status.

The organisers' parcel shapes are placeholders, so the map shows 30 of the farm's plots on outlines traced from a real
orthophoto of Wielkopolska (tools/make_farm_layout.py). The location is illustrative; every colour and hover value
(crop, real area, soil, status) comes from the data and the engine.
"""
import json
from pathlib import Path

import plotly.graph_objects as go

ASSETS = Path(__file__).resolve().parents[1] / "assets"
LAYOUT = ASSETS / "farm_layout.json"
COLORS = {"GO": "#1a9850", "CAUTION": "#f5a623", "NO-GO": "#d73027", "not available": "#9e9e9e"}
FILL = {"GO": "rgba(26,152,80,0.38)", "CAUTION": "rgba(245,166,35,0.42)", "NO-GO": "rgba(215,48,39,0.45)",
        "not available": "rgba(158,158,158,0.35)"}
CROP_SHORT = {"BARL": "barley", "COWT": "wheat", "RAPE": "rapeseed", "MAIZ": "maize", "SUNF": "sunflower",
              "HAY": "grass", "OLIV": "olives"}


def layout() -> dict | None:
    return json.loads(LAYOUT.read_text()) if LAYOUT.exists() else None


def _centroid(xs, ys):
    xs, ys = xs[:-1], ys[:-1]
    a = cx = cy = 0.0
    for i in range(len(xs)):
        j = (i + 1) % len(xs)
        c = xs[i] * ys[j] - xs[j] * ys[i]
        a, cx, cy = a + c, cx + (xs[i] + xs[j]) * c, cy + (ys[i] + ys[j]) * c
    return (cx / (3 * a), cy / (3 * a)) if a else (sum(xs) / len(xs), sum(ys) / len(ys))


def figure(farm, height=620, labels=None, title=None, selected=None) -> go.Figure | None:
    """farm: DataFrame with parcel_id, crop, area_ha, status; labels: parcel_id -> hover text (optional)."""
    lay = layout()
    if lay is None or "image" not in lay:
        return None
    from PIL import Image
    w, h = lay["width"], lay["height"]
    info = farm.set_index("parcel_id")
    fig = go.Figure()
    fig.add_layout_image(source=Image.open(ASSETS / lay["image"]), xref="x", yref="y", x=0, y=0, sizex=w, sizey=h,
                         sizing="stretch", layer="below", xanchor="left", yanchor="top")
    for f in lay["fields"]:
        if f["parcel_id"] not in info.index:
            continue
        r = info.loc[f["parcel_id"]]
        status = r.get("status", "not available")
        num = f["parcel_id"][-3:]
        hover = (labels or {}).get(f["parcel_id"], f"Plot {num} · {CROP_SHORT.get(r.crop, r.crop)} · {r.area_ha:.1f} ha")
        chosen = selected is not None and str(f["parcel_id"]) == str(selected)
        fig.add_trace(go.Scatter(x=f["xs"], y=f["ys"], fill="toself", mode="lines",
                                 fillcolor=FILL.get(status, FILL["not available"]),
                                 line=dict(color="#ffffff" if chosen else COLORS.get(status, COLORS["not available"]),
                                           width=5 if chosen else 2.5),
                                 hoveron="fills", hoverinfo="text",
                                 text=f"{hover}<br><b>{status}</b>" + (" · selected" if chosen else ""),
                                 showlegend=False))
        cx, cy = _centroid(f["xs"], f["ys"])
        fig.add_annotation(x=cx, y=cy, text=f"<b>{num}</b>", showarrow=False, font=dict(size=11, color="white"),
                           bgcolor="rgba(0,0,0,0.45)", borderpad=2)
    for s, c in COLORS.items():                                     # legend
        fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers", marker=dict(size=12, color=c, symbol="square"),
                                 name=s, showlegend=True))
    fig.add_annotation(x=w - 6, y=h - 6, xanchor="right", yanchor="bottom", showarrow=False,
                       text=lay.get("attribution", ""), font=dict(size=9, color="white"), bgcolor="rgba(0,0,0,0.4)")
    fig.add_shape(type="line", x0=40, x1=240, y0=h - 30, y1=h - 30, line=dict(color="white", width=3))   # 500 m bar
    fig.add_annotation(x=140, y=h - 34, yanchor="bottom", showarrow=False, text="500 m",
                       font=dict(size=10, color="white"))
    fig.update_xaxes(visible=False, range=[0, w], constrain="domain")
    fig.update_yaxes(visible=False, range=[h, 0], scaleanchor="x", scaleratio=1, constrain="domain")
    fig.update_layout(height=height, margin=dict(l=0, r=0, t=40 if title else 28, b=0), title=title,
                      plot_bgcolor="rgba(0,0,0,0)", legend=dict(orientation="h", y=1.0, yanchor="bottom", x=0.0,
                                                       bgcolor="rgba(0,0,0,0)"), dragmode="pan")
    return fig


def render_decision(farm=None, selected=None, real: bool = False, height: int = 480) -> None:
    """Today: show where you can go, then pick a plot. Stub mode uses the demo picture."""
    import streamlit as st

    st.caption("Green = go · yellow = only with care · red = stay off.")
    st.caption("The machine above colours the fields. Pick a plot below for the full verdict.")
    fig = None
    if real and farm is not None and "status" in getattr(farm, "columns", []):
        fig = figure(farm, height=height, selected=selected)
    if fig is not None:
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        return
    demo = ASSETS / "farm_map_demo.jpg"
    if demo.is_file():
        st.image(str(demo), width="stretch")
        pick = f" Selected: plot {str(selected)[-3:]}." if selected else ""
        st.caption("Demo holding on 11 Oct 2016, tractor and drill (M2): 16 plots GO, 7 CAUTION, 7 NO-GO. "
                   "The place is illustrative (GUGiK, geoportal.gov.pl)." + pick)
    else:
        st.info("Farm map is missing (app/assets/farm_map_demo.jpg).")
