"""Within-plot zones for the 30 plots of the farm map, from real Copernicus data over the orthophoto area.

Same method as the validation field (Gąsawy), now per plot:
  wetness after rain  Sentinel-1 VV (gamma0, dB), change 29 Sep -> 5 Oct 2016 (ascending orbit, ~37 mm of rain),
                      terciles inside the plot: wettest / normal / drier; persistence from 11 Oct.
  productivity        Sentinel-2 L2A NDVI (75th percentile of clear pixels, 15 Apr - 30 Jun), closed-canopy years
                      only (plot median >= 0.6), each year / plot median, median over years, terciles: lower / average /
                      higher; year-to-year Spearman rank correlation as a stability check.
Grid: 400 x 260 cells of 10 m over the orthophoto bbox (EPSG:3857), aligned with app/assets/farm_ortho.jpg (4 px/cell).
Values are smoothed with a 5 x 5 median (50 m) before zoning. Cells within 10 m of the outline are dropped (headlands, mixed pixels) unless the plot would get < 40 cells.

Run:  CDSE_CLIENT_ID=... CDSE_CLIENT_SECRET=... python tools/make_plot_zones.py [raster_cache_dir]
Writes app/assets/plot_zones.npz (zone grids per plot) and app/assets/plot_zones.json (stats per plot).
"""
import io
import json
import math
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
from matplotlib.path import Path as MPath
from scipy import ndimage as ndi
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "app" / "assets"
GW, GH, CELL = 400, 260, 4                      # grid cells; ortho px per cell (1600 x 1040 image)
CENTRE, HALF_M = (52.05, 16.75), (2000, 1300)
S1_DATES = ("2016-09-29", "2016-10-05", "2016-10-11")
YEARS = range(2017, 2025)
NDVI_EVAL = """//VERSION=3
function setup(){return {input:[{bands:["B04","B08","SCL","dataMask"]}],output:{bands:2,sampleType:"FLOAT32"},mosaicking:"ORBIT"};}
function evaluatePixel(samples){var v=[];for(var i=0;i<samples.length;i++){var s=samples[i];if(!s.dataMask)continue;
 if(s.SCL==4||s.SCL==5){var d=s.B08+s.B04;if(d>0)v.push((s.B08-s.B04)/d);}}
 if(v.length==0)return [NaN,0];v.sort(function(a,b){return a-b});var k=Math.floor(0.75*(v.length-1));return [v[k],v.length];}"""
VV_EVAL = """//VERSION=3
function setup(){return {input:[{bands:["VV","dataMask"]}],output:{bands:1,sampleType:"FLOAT32"}};}
function evaluatePixel(s){return s.dataMask?[10*Math.log(s.VV)/Math.LN10]:[NaN];}"""


def bbox_3857():
    lat, lon = CENTRE
    r = 6378137
    x, y = r * math.radians(lon), r * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))
    k = 1 / math.cos(math.radians(lat))
    return [x - HALF_M[0] * k, y - HALF_M[1] * k, x + HALF_M[0] * k, y + HALF_M[1] * k]


def fetch(cache: Path):
    import tifffile
    tok = json.load(urllib.request.urlopen(urllib.request.Request(
        "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token",
        data=urllib.parse.urlencode({"grant_type": "client_credentials", "client_id": os.environ["CDSE_CLIENT_ID"],
                                     "client_secret": os.environ["CDSE_CLIENT_SECRET"]}).encode())))["access_token"]

    def proc(data, evalscript, name):
        body = {"input": {"bounds": {"bbox": bbox_3857(), "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/3857"}},
                          "data": [data]},
                "output": {"width": GW, "height": GH, "responses": [{"identifier": "default", "format": {"type": "image/tiff"}}]},
                "evalscript": evalscript}
        req = urllib.request.Request("https://sh.dataspace.copernicus.eu/api/v1/process", data=json.dumps(body).encode(),
                                     headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json",
                                              "Accept": "image/tiff"})
        with urllib.request.urlopen(req, timeout=180) as r:
            np.save(cache / name, tifffile.imread(io.BytesIO(r.read())))

    for d in S1_DATES:
        proc({"type": "sentinel-1-grd", "dataFilter": {"timeRange": {"from": d + "T00:00:00Z", "to": d + "T23:59:59Z"},
              "acquisitionMode": "IW", "polarization": "DV", "orbitDirection": "ASCENDING"},
              "processing": {"backCoeff": "GAMMA0_TERRAIN", "orthorectify": True, "demInstance": "COPERNICUS_30",
                             "speckleFilter": {"type": "LEE", "windowSizeX": 3, "windowSizeY": 3}}}, VV_EVAL, f"vv_{d}.npy")
    for y in YEARS:
        proc({"type": "sentinel-2-l2a", "dataFilter": {"timeRange": {"from": f"{y}-04-15T00:00:00Z",
              "to": f"{y}-06-30T23:59:59Z"}, "maxCloudCoverage": 70}}, NDVI_EVAL, f"ndvi_{y}.npy")


def plot_mask(xs, ys):
    cx, cy = np.meshgrid((np.arange(GW) + 0.5) * CELL, (np.arange(GH) + 0.5) * CELL)
    inside = MPath(np.c_[xs, ys]).contains_points(np.c_[cx.ravel(), cy.ravel()]).reshape(GH, GW)
    core = ndi.binary_erosion(inside)
    return core if core.sum() >= 40 else inside


def smooth(values):
    """5 x 5 median (50 m): radar speckle and single-pixel noise would otherwise dominate the terciles."""
    return ndi.median_filter(np.where(np.isfinite(values), values, np.nanmedian(values)), size=5)


def terciles(values, mask, hi_is_zone0: bool):
    values = smooth(values)
    v = values[mask]
    q = np.nanpercentile(v, [100 / 3, 200 / 3])
    z = np.full(values.shape, -1, np.int8)
    lo, mid, hi = values < q[0], (values >= q[0]) & (values < q[1]), values >= q[1]
    order = (hi, mid, lo) if hi_is_zone0 else (lo, mid, hi)
    for k, sel in enumerate(order):
        z[mask & sel & np.isfinite(values)] = k
    return z


def main(cache: Path):
    cache.mkdir(parents=True, exist_ok=True)
    if not (cache / "vv_2016-09-29.npy").exists():
        fetch(cache)
    vv = {d: np.load(cache / f"vv_{d}.npy") for d in S1_DATES}
    ndvi = {y: np.load(cache / f"ndvi_{y}.npy")[..., 0] for y in YEARS}
    d_wet = vv["2016-10-05"] - vv["2016-09-29"]
    d_later = vv["2016-10-11"] - vv["2016-09-29"]
    lay = json.loads((ASSETS / "farm_layout.json").read_text())
    grids, stats = {}, {}
    for f in lay["fields"]:
        pid = f["parcel_id"]
        m = plot_mask(f["xs"], f["ys"])
        wet = terciles(d_wet, m, hi_is_zone0=True)               # 0 = wettest (largest backscatter rise)
        rel, yrs = [], []
        for y, a in ndvi.items():
            med = np.nanmedian(a[m])
            if med >= 0.6:
                rel.append(a / med)
                yrs.append(y)
        st = {"cells": int(m.sum()), "wet_change_db": round(float(np.nanmean(d_wet[m])), 2),
              "wet_change_11oct_db": round(float(np.nanmean(d_later[m])), 2),
              "wet_zone_change_db": [round(float(np.nanmean(d_wet[wet == k])), 2) for k in range(3)],
              "wet_zone_change_11oct_db": [round(float(np.nanmean(d_later[wet == k])), 2) for k in range(3)],
              "wet_share": [round(float((wet == k).sum() / max(1, (wet >= 0).sum())), 3) for k in range(3)]}
        prod = np.full(m.shape, -1, np.int8)
        if len(rel) >= 3:
            rel = np.array(rel)
            medrel = np.nanmedian(rel, axis=0)
            prod = terciles(medrel, m, hi_is_zone0=False)        # 0 = lower productivity
            ok = m & np.isfinite(rel).all(axis=0)
            pairs = [spearmanr(rel[i][ok], rel[j][ok]).correlation for i in range(len(rel)) for j in range(i + 1, len(rel))]
            st.update({"ndvi_years": yrs, "ndvi_zone_rel": [round(float(np.nanmean(medrel[prod == k]) - 1) * 100, 1)
                                                           for k in range(3)],
                       "ndvi_year_corr": round(float(np.nanmedian(pairs)), 2),
                       "prod_share": [round(float((prod == k).sum() / max(1, (prod >= 0).sum())), 3) for k in range(3)],
                       "wet_in_low_prod": round(float(((wet == 0) & (prod == 0)).sum() / max(1, (prod == 0).sum())), 2)})
        else:
            st.update({"ndvi_years": yrs, "note": "fewer than 3 closed-canopy springs: no productivity zones"})
        ys_, xs_ = np.where(m)
        box = [int(xs_.min()), int(ys_.min()), int(xs_.max()) + 1, int(ys_.max()) + 1]
        st["box"] = box
        grids[pid + "|wet"] = wet[box[1]:box[3], box[0]:box[2]]
        grids[pid + "|prod"] = prod[box[1]:box[3], box[0]:box[2]]
        stats[pid] = st
    np.savez_compressed(ASSETS / "plot_zones.npz", **grids)
    (ASSETS / "plot_zones.json").write_text(json.dumps({
        "grid": {"w": GW, "h": GH, "cell_m": 10, "ortho_px_per_cell": CELL},
        "sources": "Contains modified Copernicus Sentinel data [2016-2024], CDSE Process API",
        "s1_dates": list(S1_DATES), "plots": stats}, indent=0))
    print(len(stats), "plots")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / ".cache" / "zones")
