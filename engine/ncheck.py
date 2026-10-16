"""N check (owner: Marek, Add-on 2). Spec 6.5, 6.7, 7.10: risk of losing applied nitrogen, from the weather
around the application date. Prototype: percentages are indicative ranges, shown with a 'prototype' label.

Order of the rules (first match wins):
  prohibited  date in the closed period (default 1 Dec - 31 Jan, verify per country) or frozen soil (Tmax <= 0 °C)
  high        any day with >= 20 mm rain from the application day to +3 days (leaching / runoff): 20-30 % of N
  medium      < 5 mm rain in the next 10 days (volatilisation, no uptake): 10-15 % of N
  low         none of the above
The 'surface-applied urea or organic N' condition of 6.7 is not applied: the dataset has no urea flag, and the
pre-event test (1 high, 33 medium of 127 spring applications) counted every application.
"""
from __future__ import annotations

import pandas as pd

from engine import params as prm

ORIGIN = "real+synthetic+assumption"
NA = "not available"


def _closed(d: pd.Timestamp) -> bool:
    cp = prm.CLOSED_PERIOD_DEFAULT.value
    md = d.strftime("%m-%d")
    return (cp["start"] <= md <= cp["end"]) if cp["start"] <= cp["end"] else (md >= cp["start"] or md <= cp["end"])


def n_check(app_date, n_kg_ha, weather: pd.DataFrame, product_type: str | None = None,
            method: str | None = None) -> dict:
    """Risk badge for one N application. weather: date, precip_mm, tmax_c (regional, replay)."""
    d = pd.Timestamp(app_date)
    hr, nu = prm.N_RULES["heavy_rain"], prm.N_RULES["no_uptake"]
    base = {"date": d, "n_kg_ha": n_kg_ha, "label": "prototype", "origin": ORIGIN}
    if n_kg_ha is None or pd.isna(n_kg_ha) or n_kg_ha <= 0:
        return {**base, "risk": "not applicable", "reason": "No nitrogen in this application",
                "n_at_risk_kg_ha": "not applicable"}
    w = weather.set_index(pd.to_datetime(weather["date"]))
    horizon = max(hr["days"].value, nu["days"].value)
    days = pd.date_range(d, d + pd.Timedelta(days=horizon))
    if not set(days).issubset(w.index) or w.loc[days, "precip_mm"].isna().any():
        return {**base, "risk": NA, "reason": f"No weather for {d:%d %b %Y} + {horizon} days",
                "n_at_risk_kg_ha": NA}
    tmax = float(w.loc[d, "tmax_c"])
    rain_0_3 = w.loc[pd.date_range(d, d + pd.Timedelta(days=hr["days"].value)), "precip_mm"]
    rain_next = float(w.loc[pd.date_range(d + pd.Timedelta(days=1), d + pd.Timedelta(days=nu["days"].value)),
                            "precip_mm"].sum())
    out = {**base, "tmax_c": tmax, "rain_0_3_max_mm": float(rain_0_3.max()), "rain_0_3_sum_mm": float(rain_0_3.sum()),
           "rain_next10_mm": rain_next}

    def at_risk(pct):
        lo, hi = pct
        return (round(n_kg_ha * lo / 100, 1), round(n_kg_ha * hi / 100, 1))

    if _closed(d):
        return {**out, "risk": "prohibited", "n_at_risk_kg_ha": "not applicable",
                "reason": f"{d:%d %b} is in the closed period for N (default 1 Dec - 31 Jan, verify per country)"}
    if tmax <= prm.FROST["tmax_c"].value:
        return {**out, "risk": "prohibited", "n_at_risk_kg_ha": "not applicable",
                "reason": f"Frozen soil (Tmax {tmax:.1f} °C): no fertilising"}
    if rain_0_3.max() >= hr["rain_mm"].value:
        wettest = rain_0_3.idxmax()
        return {**out, "risk": "high", "n_at_risk_kg_ha": at_risk(hr["n_at_risk_pct"].value),
                "reason": f"{rain_0_3.max():.0f} mm of rain on {wettest:%d %b} ({rain_0_3.sum():.0f} mm in days 0-3): "
                          "leaching and runoff"}
    if rain_next < nu["rain_mm_lt"].value:
        return {**out, "risk": "medium", "n_at_risk_kg_ha": at_risk(nu["n_at_risk_pct"].value),
                "reason": f"Only {rain_next:.1f} mm of rain in the next 10 days: N stays on the surface "
                          "(volatilisation, no uptake)"}
    return {**out, "risk": "low", "n_at_risk_kg_ha": None,
            "reason": f"No heavy rain in days 0-3 and {rain_next:.0f} mm in the next 10 days to move N to the roots"}
