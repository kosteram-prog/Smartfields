"""Day status rules: GO / CAUTION / NO-GO per parcel, day, machine load class (spec 6.4, 7.3).

Written by Marek's agent for Mirela's slice (agreed 16 Oct 20:22); Mirela reviews.

  axle_load_class(machine_id, load_pct)                       -> (load class, axle load t)
  classify_day(rwc_eff, clay, sand, rain_today, rain_prev24h, tmax, load_class, passes, operation) -> dict
  status_table(soil_water_df, parcels, load_class, passes, operation) -> df + status, access, suitability, risk, reasons

Rules (all values in params.py):
  1. thresholds on RWC_eff per load class (6.4), texture adjustment (clay >= 30 %: -0.05, sand >= 70 %: +0.05),
     each extra pass on the same day: -0.03
  2. frozen soil (Tmax <= 0 °C): a status set only by soil wetness becomes GO for L1-L3 (frozen soil carries the load)
  3. rain overrides: >= 5 mm today -> NO-GO; >= 10 mm in the previous 24 h -> at best CAUTION
  4. suitability: any fertilising on frozen soil -> NO-GO (other operation rules live in engine.today)
  status = the worse of access and suitability
Risk 0-100 (7.3): 100 x clip((RWC_eff - (GO threshold - 0.2)) / 0.4, 0, 1); a NO-GO is at least 65.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from engine import params as prm

ORIGIN = "modelled"
STATUSES = np.array(["GO", "CAUTION", "NO-GO"])
FROST_RISK_NOGO_MIN = 65          # spec 7.3: overrides force a NO-GO risk to at least 65
RISK_SPAN, RISK_BELOW_GO = 0.4, 0.2   # spec 7.3 risk formula constants


def axle_load_class(machine_id: str, load_pct: float) -> tuple[str, float]:
    """Max axle load scales linearly from empty (empty_share x loaded) to fully loaded (spec 6.1)."""
    m = prm.MACHINES[machine_id]
    loaded, share = m["max_axle_t"].value, m["empty_share"].value
    load = min(max(float(load_pct), 0.0), 100.0)
    axle = loaded * (share + (1 - share) * load / 100.0)
    if load >= 100:                    # the 6.1 table gives the class at full load (8 t = L3, 10 t = L5)
        return m["load_class"], round(axle, 2)
    for cls, p in prm.LOAD_CLASS_BOUNDS.items():
        lo, hi = p.value
        if lo < axle <= hi or (cls == "L1" and axle <= hi):
            return cls, round(axle, 2)
    return "L5", round(axle, 2)


def _thresholds(load_class, clay, sand, passes):
    t = prm.THRESHOLDS[load_class]
    ta = prm.TEXTURE_ADJUSTMENT
    adj = (np.where(clay >= ta["clay_min_pct"].value, ta["clay_delta"].value, 0.0)
           + np.where(sand >= ta["sand_min_pct"].value, ta["sand_delta"].value, 0.0)
           + (np.asarray(passes) - 1) * prm.PASSES["threshold_delta_per_extra_pass"].value)
    return t["go"].value + adj, t["caution"].value + adj


def _classify(rwc, clay, sand, rain_today, rain_prev24, tmax, load_class, passes, operation):
    """Vectorised core. Returns dict of arrays: access, suitability, status (ints 0/1/2), risk, plus flags."""
    rwc, clay, sand = (np.asarray(x, dtype=float) for x in (rwc, clay, sand))
    rain_today, rain_prev24, tmax = (np.asarray(x, dtype=float) for x in (rain_today, rain_prev24, tmax))
    go, caution = _thresholds(load_class, clay, sand, passes)
    soil = np.where(rwc <= go, 0, np.where(rwc <= caution, 1, 2))
    frozen = tmax <= prm.FROST["tmax_c"].value
    frost_ok = frozen & (load_class in prm.FROST["traffic_go_classes"].value)
    access = np.where(frost_ok, 0, soil)
    rain_nogo = rain_today >= prm.RAIN_OVERRIDES["rain_today_nogo_mm"].value
    rain_cap = rain_prev24 >= prm.RAIN_OVERRIDES["rain_prev24h_caution_mm"].value
    access = np.where(rain_nogo, 2, np.where(rain_cap, np.maximum(access, 1), access))
    fert_frozen = frozen & (operation == "fertilising") & bool(prm.FROST["fertilising_nogo"].value)
    suit = np.where(fert_frozen, 2, 0)
    status = np.maximum(access, suit)
    risk = 100 * np.clip((rwc - (go - RISK_BELOW_GO)) / RISK_SPAN, 0, 1)
    risk = np.where(frost_ok & ~rain_nogo, np.minimum(risk, 40), risk)
    risk = np.where(status == 2, np.maximum(risk, FROST_RISK_NOGO_MIN), risk)
    return dict(access=access, suit=suit, status=status, risk=np.round(risk).astype(int), go=go, caution=caution,
                soil=soil, frost_ok=frost_ok, rain_nogo=rain_nogo, rain_cap=rain_cap, fert_frozen=fert_frozen,
                rwc=rwc, clay=clay, sand=sand, rain_today=rain_today, rain_prev24=rain_prev24, tmax=tmax)


def _reasons(c: dict, i: int, load_class: str, passes: int) -> list[str]:
    r = []
    soil_word = STATUSES[c["soil"][i]]
    tex = ""
    if c["clay"][i] >= prm.TEXTURE_ADJUSTMENT["clay_min_pct"].value:
        tex = f" on clay {c['clay'][i]:.0f}%"
    elif c["sand"][i] >= prm.TEXTURE_ADJUSTMENT["sand_min_pct"].value:
        tex = f" on sand {c['sand'][i]:.0f}%"
    r.append(f"Soil water RWC_eff {c['rwc'][i]:.2f} vs GO <= {c['go'][i]:.2f}, CAUTION <= {c['caution'][i]:.2f} "
             f"for {load_class}{tex} -> {soil_word}")
    if passes > 1:
        r.append(f"{passes} passes: thresholds {abs(prm.PASSES['threshold_delta_per_extra_pass'].value) * (passes - 1):.2f} stricter")
    if c["frost_ok"][i] and c["soil"][i] > 0:
        r.append(f"Frozen soil (Tmax {c['tmax'][i]:.1f} °C) carries {load_class} traffic")
    if c["rain_nogo"][i]:
        r.append(f"Rain today {c['rain_today'][i]:.1f} mm (>= {prm.RAIN_OVERRIDES['rain_today_nogo_mm'].value:g} mm): NO-GO")
    elif c["rain_cap"][i]:
        r.append(f"Rain in the previous 24 h {c['rain_prev24'][i]:.1f} mm: at best CAUTION")
    if c["fert_frozen"][i]:
        r.append(f"Frozen soil (Tmax {c['tmax'][i]:.1f} °C): no fertilising")
    return r


def classify_day(rwc_eff, clay_pct, sand_pct, rain_today_mm, rain_prev24h_mm, tmax_c, load_class,
                 passes=1, operation="sowing") -> dict:
    c = _classify([rwc_eff], [clay_pct], [sand_pct], [rain_today_mm], [rain_prev24h_mm], [tmax_c],
                  load_class, passes, operation)
    return {"status": str(STATUSES[c["status"][0]]), "access": str(STATUSES[c["access"][0]]),
            "suitability": str(STATUSES[c["suit"][0]]), "risk": int(c["risk"][0]),
            "reasons": _reasons(c, 0, load_class, int(passes)), "origin": ORIGIN}


def status_table(soil_water_df: pd.DataFrame, parcels: pd.DataFrame, load_class: str, passes: int = 1,
                 operation: str = "sowing") -> pd.DataFrame:
    """Vectorised classify_day for a whole soil-water table (rows keep their order)."""
    tex = parcels.set_index("parcel_id")[["clay_pct", "sand_pct"]]
    out = soil_water_df.copy()
    clay = out["parcel_id"].map(tex["clay_pct"]).to_numpy(dtype=float)
    sand = out["parcel_id"].map(tex["sand_pct"]).to_numpy(dtype=float)
    c = _classify(out["RWC_eff"], clay, sand, out["rain_today_mm"], out["rain_prev24h_mm"], out["tmax_c"],
                  load_class, passes, operation)
    out["status"] = STATUSES[c["status"]]
    out["access"] = STATUSES[c["access"]]
    out["suitability"] = STATUSES[c["suit"]]
    out["risk"] = c["risk"]
    out["reasons"] = [_reasons(c, i, load_class, int(passes)) for i in range(len(out))]
    missing = out["RWC_eff"].isna().to_numpy() | np.isnan(clay) | np.isnan(sand)
    if missing.any():                                   # no soil data: not available, never a guess
        out.loc[missing, ["status", "access", "suitability"]] = "not available"
        out.loc[missing, "risk"] = pd.NA
    return out
