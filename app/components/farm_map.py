"""Farm map: illustrative rural layout (app/assets/farm_layout.json) coloured by the engine's status.

The organisers' parcel shapes are scattered squares, so the map uses an illustrative layout: 30 fields placed between
roads, a woodland, a stream and the farmstead. Every colour and hover value (crop, real area, soil, status) comes from
the data and the engine; only the geometry and the field sizes on the map are illustrative.
"""
import json
from pathlib import Path

import plotly.graph_objects as go

LAYOUT = Path(__file__).resolve().parents[1] / "assets" / "farm_layout.json"
COLORS = {"GO": "#1a9850", "CAUTION": "#f5a623", "NO-GO": "#d73027", "not available": "#9e9e9e"}
CROP_SHORT = {"BARL": "barley", "COWT": "wheat", "RAPE": "rapeseed", "MAIZ": "maize", "SUNF": "sunflower",
              "HAY": "grass", "OLIV": "olives"}


def layout() -> dict | None:
    return json.loads(LAYOUT.read_text()) if LAYOUT.exists() else None


def _line(fig, pts, colour, width, name, dash=None):
    fig.add_trace(go.Scatter(x=pts["xs"], y=pts["ys"], mode="lines", line=dict(color=colour, width=width, dash=dash),
                             hoverinfo="skip", showlegend=False, name=name))


def _area(fig, pts, colour, line, name):
    fig.add_trace(go.Scatter(x=pts["xs"], y=pts["ys"], fill="toself", mode="lines", fillcolor=colour,
                             line=dict(color=line, width=1), hoverinfo="text", text=name, hoveron="fills",
                             showlegend=False))


def figure(farm, height=560, labels=None, title=None) -> go.Figure | None:
    """farm: DataFrame with parcel_id, crop, area_ha, status; labels: parcel_id -> hover text (optional)."""
    lay = layout()
    if lay is None:
        return None
    info = farm.set_index("parcel_id")
    fig = go.Figure()
    _area(fig, lay["village"], "#e8dfd0", "#cbbfa8", "Village")
    _area(fig, lay["wood"], "#7fa36b", "#5e844c", "Woodland")
    _line(fig, lay["stream"], "#7fb3d5", 5, "Stream")
    _line(fig, lay["road"], "#b9b2a5", 9, "Road")
    _line(fig, lay["track"], "#d8cfbd", 4, "Field track", dash="dot")
    if "lane" in lay:
        _line(fig, lay["lane"], "#b9b2a5", 6, "Farm lane")
    for f in lay["fields"]:
        if f["parcel_id"] not in info.index:
            continue
        r = info.loc[f["parcel_id"]]
        status = r.get("status", "not available")
        colour = COLORS.get(status, COLORS["not available"])
        num = f["parcel_id"][-3:]
        hover = (labels or {}).get(f["parcel_id"], f"Field {num} · {CROP_SHORT.get(r.crop, r.crop)} · {r.area_ha:.1f} ha")
        fig.add_trace(go.Scatter(x=f["xs"], y=f["ys"], fill="toself", mode="lines", fillcolor=colour, opacity=0.88,
                                 line=dict(color="#fbfaf5", width=2), hoveron="fills", hoverinfo="text",
                                 text=f"{hover}<br><b>{status}</b>", showlegend=False))
        cx, cy = sum(f["xs"][:-1]) / 4, sum(f["ys"][:-1]) / 4
        w = max(f["xs"]) - min(f["xs"])
        small = w < 230
        fig.add_annotation(x=cx, y=cy, showarrow=False, font=dict(size=9 if small else 11, color="white"),
                           text=f"<b>{num}</b>" if small else f"<b>{num}</b><br>{CROP_SHORT.get(r.crop, r.crop)}")
    # farmstead: yard + buildings
    _area(fig, lay["farmyard"], "#d9cbb3", "#a8977b", "Farmstead")
    xs, ys = lay["farmyard"]["xs"], lay["farmyard"]["ys"]
    fig.add_trace(go.Scatter(x=[sum(xs[:-1]) / 4], y=[sum(ys[:-1]) / 4], mode="markers+text", text=["Farm"],
                             textposition="top center", marker=dict(symbol="square", size=12, color="#8c4a2f"),
                             hoverinfo="text", hovertext=["Farmstead (machinery yard)"], showlegend=False))
    vx, vy = lay["village"]["xs"], lay["village"]["ys"]
    fig.add_annotation(x=sum(vx[:-1]) / 4, y=sum(vy[:-1]) / 4, text="village", showarrow=False,
                       font=dict(size=10, color="#7a6e5a"))
    wx, wy = lay["wood"]["xs"], lay["wood"]["ys"]
    fig.add_annotation(x=sum(wx[:-1]) / 5, y=sum(wy[:-1]) / 5, text="woodland", showarrow=False,
                       font=dict(size=10, color="#f2f5ee"))
    for s, c in COLORS.items():                                     # legend
        fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers", marker=dict(size=12, color=c, symbol="square"),
                                 name=s, showlegend=True))
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False, scaleanchor="x", scaleratio=1)
    fig.update_layout(height=height, margin=dict(l=0, r=0, t=40 if title else 0, b=0), plot_bgcolor="#eef0dc",
                      paper_bgcolor="#eef0dc", title=title,
                      legend=dict(orientation="h", y=1.02 if not title else 1.0, x=0.0, bgcolor="rgba(0,0,0,0)"))
    return fig
