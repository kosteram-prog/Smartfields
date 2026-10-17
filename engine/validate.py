"""Does the model agree with the satellite? (B5, 17 Oct). Real field Gasawy 28, October 2016.

The same soil-water bucket as the demo farm, on the real field's regional SoilGrids topsoil and PL418 AgERA5 weather,
compared with the field-mean Sentinel-1 VV backscatter on 8 dates. Radar responds to surface moisture but also to
roughness and residue: the comparison is "consistent with the model", not proof.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from engine import params as prm


SOIL_LEVELS = (("measured", "measured on the plot"), ("soilgrids_point", "SoilGrids 250 m at the plot point"))


def field_soil(measured: dict | None = None) -> dict:
    """Best available texture for the real field: user input > params measured > SoilGrids point > regional mean."""
    from engine import data
    candidates = [("measured on the plot (your input)", measured, "real")]
    candidates += [(label, prm.REAL_FIELD_SOIL[key].value, prm.REAL_FIELD_SOIL[key].origin) for key, label in SOIL_LEVELS]
    for label, tex, origin in candidates:
        if tex and all(tex.get(k) is not None for k in ("clay_pct", "sand_pct", "om_pct")):
            return {"clay_pct": float(tex["clay_pct"]), "sand_pct": float(tex["sand_pct"]), "om_pct": float(tex["om_pct"]),
                    "source": label, "origin": origin, "level": label.split(" (")[0]}
    reg = data.load_regional_soil(prm.REAL_FIELD["nuts3"].value)
    return {**{k: reg[k] for k in ("clay_pct", "sand_pct", "om_pct")}, "origin": "modelled", "level": "regional",
            "source": f"regional mean, {reg['source']} - no field-level soil data yet"}


def radar_vs_model(start: str = "2016-09-25", end: str = "2016-10-20", measured: dict | None = None) -> dict:
    """measured: optional {"clay_pct", "sand_pct", "om_pct"} from a soil analysis of the field (overrides the rest)."""
    from engine import data, soil, status
    nuts3 = prm.REAL_FIELD["nuts3"].value
    tex = field_soil(measured)
    field = pd.DataFrame([{"parcel_id": "GASAWY-28", "crop": "field", "area_ha": prm.REAL_FIELD["area_ha"].value,
                           "clay_pct": tex["clay_pct"], "sand_pct": tex["sand_pct"], "om_pct": tex["om_pct"]}])
    field = soil.add_hydraulics(field)
    wx = data.load_weather(nuts3)
    sw = soil.soil_water(field, wx)
    lc = {k: status.status_table(sw, field, k).status.to_numpy() for k in ("L2", "L3")}
    sw = sw.assign(status_L2=lc["L2"], status_L3=lc["L3"])
    daily = sw[(sw.date >= start) & (sw.date <= end)].reset_index(drop=True)
    vv = pd.DataFrame(prm.S1_GASAWY_VV.value, columns=["date", "orbit", "vv_db"])
    vv["date"] = pd.to_datetime(vv["date"])
    m = vv.merge(daily[["date", "RWC", "RWC_eff", "rain_today_mm", "rain_prev48h_mm", "status_L2", "status_L3"]],
                 on="date", how="left")
    same = m[m.orbit == "asc A"]

    def spearman(a, b):
        return float(pd.Series(a).rank().corr(pd.Series(b).rank())) if len(a) >= 3 else float("nan")

    return {
        "field": {"name": prm.REAL_FIELD["name"].value, "area_ha": prm.REAL_FIELD["area_ha"].value, "nuts3": nuts3,
                  **{k: tex[k] for k in ("clay_pct", "sand_pct", "om_pct")}, "soil_source": tex["source"],
                  "soil_level": tex["level"],
                  "fc_mm": round(float(field.fc_mm.iloc[0]), 1), "wp_mm": round(float(field.wp_mm.iloc[0]), 1)},
        "daily": daily, "radar": m,
        "spearman_all": spearman(m.vv_db, m.RWC_eff), "spearman_same_orbit": spearman(same.vv_db, same.RWC_eff),
        "n_dates": int(len(m)), "n_same_orbit": int(len(same)),
        "vv_change_db": float(m.loc[m.date == "2016-10-05", "vv_db"].iloc[0] - m.loc[m.date == "2016-09-29", "vv_db"].iloc[0]),
        "origin": "real+" + tex["origin"] if tex["origin"] != "real" else "real",
        "caveat": "Radar responds to surface moisture but also to roughness and residue; orbits differ in geometry.",
    }
