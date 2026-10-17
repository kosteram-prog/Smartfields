"""How robust are the numbers? (B7, 17 Oct). One assumption changed at a time, everything recomputed live.

Variants in params.SENSITIVITY_VARIANTS (the pre-event sensitivity test). For each: P(finish by deadline), 2016
completion, workable days 1-21 Oct 2016, smallest contractor step reaching 90 %, weather cost of delay (median, 2016),
and the 13 Oct 2016 demo statuses (clay 0149869 and sand 0149906, L2/L3).
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace

import pandas as pd

from engine import params as prm

CLAY, SAND = "PARCEL-0149869", "PARCEL-0149906"
SHORT = {"GO": "G", "CAUTION": "C", "NO-GO": "N", "not available": "-"}


@contextmanager
def _override(kind, value):
    """Temporarily change one parameter in params.py (restored afterwards)."""
    saved = []

    def put(d, k, new):
        saved.append((d, k, d[k]))
        d[k] = new
    if kind == "thresholds":
        for cls, t in prm.THRESHOLDS.items():
            put(t, "go", replace(t["go"], value=round(t["go"].value + value, 3)))
            put(t, "caution", replace(t["caution"], value=round(t["caution"].value + value, 3)))
    elif kind == "texture":
        ta = prm.TEXTURE_ADJUSTMENT
        put(ta, "clay_delta", replace(ta["clay_delta"], value=0.0))
        put(ta, "sand_delta", replace(ta["sand_delta"], value=0.0))
    elif kind == "transient_k":
        put(prm.BUCKET, "transient_k", replace(prm.BUCKET["transient_k"], value=value))
    elif kind == "rain_today":
        r = prm.RAIN_OVERRIDES
        put(r, "rain_today_nogo_mm", replace(r["rain_today_nogo_mm"], value=value))
    elif kind == "rain_prev24":
        r = prm.RAIN_OVERRIDES
        put(r, "rain_prev24h_caution_mm", replace(r["rain_prev24h_caution_mm"], value=value))
    try:
        yield
    finally:
        for d, k, old in reversed(saved):
            d[k] = old


def run_variant(kind, value, holding_id: str | None = None) -> dict:
    from engine import data, season, soil, status
    from engine.cost import _econ_params, season_cost
    p = season.resolve_params({"holding_id": holding_id} if holding_id else {})
    if kind == "caution_weight":
        p["caution_weight"] = value
    with _override(kind, value):
        farm = data.load_farm(p["holding_id"])
        autumn = farm[farm.crop.isin(season.autumn_crops())]
        sw = soil.soil_water(autumn, data.load_weather(p["nuts3"]))
        md = sw.date.dt.strftime("%m-%d")
        win = sw[(md >= p["window_start"]) & (md <= p["end"])]
        st_l2 = status.status_table(win, autumn, p["load_class"])[["parcel_id", "date", "status"]]
        res = season.season_from_inputs(farm, st_l2, p)
        perfect = season.season_from_inputs(farm, st_l2, p, perfect_weather=True)
        cost = season_cost(res["schedule"], farm, _econ_params({}) | {"perfect_schedule": perfect["schedule"]})
        day = win[win.date == "2016-10-13"]
        demo = {}
        for cls in ("L2", "L3"):
            s = status.status_table(day, autumn, cls).set_index("parcel_id").status
            demo[cls] = (SHORT[s.get(CLAY, "not available")], SHORT[s.get(SAND, "not available")])
    comp = res["completion"].set_index("year").completion_date
    wd = res["workable_days"]
    w16 = wd[(wd.date >= "2016-10-01") & (wd.date <= "2016-10-21")]
    py = cost["per_year"].set_index("year")
    done16 = comp.get(2016)
    return {"P": res["P_by_deadline"]["value"],
            "done_2016": done16.strftime("%d %b") if pd.notna(done16) else "not done by 30 Nov",
            "workable_days_2016": int((w16.share_go_parcels >= 0.5).sum()),
            "contractor": res["contractor_recommendation"].get("extra_ha_day"),
            "cost_median": cost["median"]["weather_default"], "cost_2016": py.loc[2016, "weather_default"],
            "demo_13oct": f"{demo['L2'][0]}/{demo['L3'][0]} · {demo['L2'][1]}/{demo['L3'][1]}"}


def run_all(holding_id: str | None = None) -> pd.DataFrame:
    rows = []
    for label, kind, value in prm.SENSITIVITY_VARIANTS.value:
        rows.append({"variant": label, **run_variant(kind, value, holding_id)})
    return pd.DataFrame(rows)
