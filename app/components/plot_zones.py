"""Plot zones: farm overview on the orthophoto, then one plot zoomed with its within-plot zones.

Zones are real Copernicus data over the orthophoto area (tools/make_plot_zones.py): Sentinel-1 wetness change after
the rain of early October 2016 and Sentinel-2 productivity over 2017-2024. They show WHERE inside a plot to be careful,
never WHETHER to go (that is the day status).
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import numpy as np
import plotly.graph_objects as go
from PIL import Image, ImageDraw

from components import farm_map

ASSETS = Path(__file__).resolve().parents[1] / "assets"

LAYERS = {
    "wet": {"title": "Wetness after rain", "short": "Wet after rain",
            "sub": "Sentinel-1 radar, change 29 Sep → 5 Oct 2016 (~37 mm of rain)",
            "names": ("Wettest third", "Normal", "Driest third"),
            "colors": ((33, 102, 172), (146, 197, 222), (240, 228, 195))},
    "prod": {"title": "Productivity", "short": "Productivity",
             "sub": "Sentinel-2 NDVI in spring, closed-canopy years 2017-2024",
             "names": ("Lower", "Average", "Higher"),
             "colors": ((166, 97, 26), (246, 232, 195), (27, 120, 55))},
}


@lru_cache(maxsize=1)
def data() -> tuple[dict, dict] | None:
    js, npz = ASSETS / "plot_zones.json", ASSETS / "plot_zones.npz"
    if not (js.exists() and npz.exists()):
        return None
    grids = dict(np.load(npz))
    return json.loads(js.read_text()), grids


@lru_cache(maxsize=1)
def _ortho() -> Image.Image:
    return Image.open(ASSETS / farm_map.layout()["image"]).convert("RGBA")


def _hex(rgb, a=1.0) -> str:
    return f"rgba({rgb[0]},{rgb[1]},{rgb[2]},{a})"


def overview_value(pid: str, layer: str) -> float | None:
    d = data()
    if d is None or pid not in d[0]["plots"]:
        return None
    s = d[0]["plots"][pid]
    if layer == "wet":
        return s["wet_change_db"]
    rel = s.get("ndvi_zone_rel")
    return None if not rel else rel[2] - rel[0]


def overview_figure(farm, layer: str, selected: str | None, labels: dict, height: int = 540) -> go.Figure | None:
    """Farm map coloured by the plot-level value of the layer; markers at the centroids are clickable."""
    lay = farm_map.layout()
    if lay is None or data() is None:
        return None
    w, h = lay["width"], lay["height"]
    info = farm.set_index("parcel_id")
    vals = {f["parcel_id"]: overview_value(f["parcel_id"], layer) for f in lay["fields"]}
    finite = [v for v in vals.values() if v is not None]
    lo, hi = (min(finite), max(finite)) if finite else (0, 1)
    top = LAYERS[layer]["colors"][0] if layer == "wet" else (166, 97, 26)
    fig = go.Figure()
    fig.add_layout_image(source=Image.open(ASSETS / lay["image"]), xref="x", yref="y", x=0, y=0, sizex=w, sizey=h,
                         sizing="stretch", layer="below", xanchor="left", yanchor="top")
    mx, my, md, mt = [], [], [], []
    for f in lay["fields"]:
        pid = f["parcel_id"]
        v = vals[pid]
        t = 0.0 if v is None or hi == lo else (v - lo) / (hi - lo)
        sel = pid == selected
        fig.add_trace(go.Scatter(
            x=f["xs"], y=f["ys"], fill="toself", mode="lines", fillcolor=_hex(top, 0.12 + 0.55 * t),
            line=dict(color="#ffffff" if sel else _hex(top, 0.95), width=4 if sel else 1.6),
            hoverinfo="skip", showlegend=False))
        cx, cy = farm_map._centroid(f["xs"], f["ys"])
        unit = "dB" if layer == "wet" else "% spread"
        txt = labels.get(pid, pid)
        hv = f"{txt}<br>{LAYERS[layer]['short']}: " + ("n/a" if v is None else f"{v:+.1f} {unit}")
        mx.append(cx), my.append(cy), md.append(pid), mt.append(hv)
    fig.add_trace(go.Scatter(
        x=mx, y=my, mode="markers+text", customdata=md, hovertext=mt, hoverinfo="text",
        text=[p[-3:] for p in md], textfont=dict(color="white", size=11),
        marker=dict(size=[32 if p == selected else 26 for p in md],
                    color=["#ffffff" if p == selected else "rgba(0,0,0,0.55)" for p in md],
                    line=dict(color="white", width=1.5)),
        textposition="middle center", showlegend=False, name="plots"))
    if selected:
        i = md.index(selected) if selected in md else None
        if i is not None:
            fig.data[-1].textfont.color = ["#111" if p == selected else "white" for p in md]
    fig.add_annotation(x=w - 6, y=h - 6, xanchor="right", yanchor="bottom", showarrow=False,
                       text=lay.get("attribution", "") + " · Copernicus Sentinel data", font=dict(size=9, color="white"),
                       bgcolor="rgba(0,0,0,0.4)")
    fig.update_xaxes(visible=False, range=[0, w], constrain="domain")
    fig.update_yaxes(visible=False, range=[h, 0], scaleanchor="x", scaleratio=1, constrain="domain")
    fig.update_layout(height=height, margin=dict(l=0, r=0, t=0, b=0), plot_bgcolor="rgba(0,0,0,0)",
                      dragmode=False, clickmode="event+select")
    return fig


def zoom_image(pid: str, layer: str | None, max_w: int = 760, max_h: int = 560) -> Image.Image | None:
    """The plot cut from the orthophoto with its zones (smoothed 10 m cells); layer None: photo only."""
    lay, d = farm_map.layout(), data()
    if lay is None or d is None or pid not in d[0]["plots"]:
        return None
    f = next(x for x in lay["fields"] if x["parcel_id"] == pid)
    meta, grids = d
    s, c = meta["plots"][pid], meta["grid"]["ortho_px_per_cell"]
    x0, y0, x1, y1 = (v * c for v in s["box"])
    pad = max(24, int(0.18 * max(x1 - x0, y1 - y0)))
    X0, Y0 = max(0, x0 - pad), max(0, y0 - pad)
    X1, Y1 = min(lay["width"], x1 + pad), min(lay["height"], y1 + pad)
    base = _ortho().crop((X0, Y0, X1, Y1))
    k = min(max_w / base.width, max_h / base.height)
    size = (int(base.width * k), int(base.height * k))
    base = base.resize(size, Image.LANCZOS)
    poly = [((x - X0) * k, (y - Y0) * k) for x, y in zip(f["xs"], f["ys"])]
    pmask = Image.new("L", size, 0)
    ImageDraw.Draw(pmask).polygon(poly, fill=255)
    over = Image.new("RGBA", size, (0, 0, 0, 0))
    if layer:
        z = grids[f"{pid}|{layer}"]
        gh, gw = z.shape
        # zone grid placed on the crop; smooth class boundaries: upsample one-hot layers bicubic, take the argmax
        tgt = (max(1, int(gw * c * k)), max(1, int(gh * c * k)))
        ox, oy = int((s["box"][0] * c - X0) * k), int((s["box"][1] * c - Y0) * k)
        layers = [np.asarray(Image.fromarray(((z == i) * 255).astype(np.uint8)).resize(tgt, Image.BICUBIC), float)
                  for i in range(3)]
        valid = np.asarray(Image.fromarray(((z >= 0) * 255).astype(np.uint8)).resize(tgt, Image.BILINEAR)) > 0
        cls = np.argmax(np.stack(layers), axis=0)
        rgba = np.zeros((tgt[1], tgt[0], 4), np.uint8)
        for i, col in enumerate(LAYERS[layer]["colors"]):
            rgba[cls == i] = col + (170,)
        rgba[~valid] = 0
        zimg = Image.new("RGBA", size, (0, 0, 0, 0))
        zimg.paste(Image.fromarray(rgba, "RGBA"), (ox, oy))
        zimg.putalpha(Image.fromarray(np.minimum(np.asarray(zimg.split()[3]), np.asarray(pmask))))
        over = Image.alpha_composite(over, zimg)
        dim = Image.new("RGBA", size, (15, 15, 15, 0))
        dim.putalpha(Image.eval(pmask, lambda p: 0 if p else 120))
        over = Image.alpha_composite(over, dim)
    dr = ImageDraw.Draw(over)
    dr.line(poly, fill=(255, 255, 255, 255), width=3, joint="curve")
    out = Image.alpha_composite(base, over)
    bar = 100 / lay["m_per_px"] * k                                    # 100 m scale bar (2.5 m per ortho px)
    d2 = ImageDraw.Draw(out)
    d2.rectangle([12, size[1] - 22, 12 + bar, size[1] - 17], fill=(255, 255, 255, 235))
    d2.text((12, size[1] - 36), "100 m", fill=(255, 255, 255, 255))
    return out.convert("RGB")


def stability_word(r: float | None) -> tuple[str, str]:
    if r is None:
        return "not available", "#9e9e9e"
    if r >= 0.4:
        return "repeats year to year", "#1b7837"
    if r >= 0.2:
        return "weak pattern", "#b8860b"
    return "no stable pattern", "#9e9e9e"
