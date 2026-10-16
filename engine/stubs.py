"""STUBS - replace with real functions.

Fake but realistic outputs for every function of the engine contract, built from the
pre-event demo numbers (FARM-13525, replay 13 Oct 2016). Same names and signatures as the
real functions, so pages can call `stubs.<fn>` now and switch to the real module later.
Origin labels: dict outputs carry an `origin` key, DataFrames an `origin` column.
Only the demo cases are meaningful; anything else returns plausible filler or "not available".
"""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

from engine import params as prm

NA = "not available"
YEARS = list(prm.SEASON["years"].value)
_DEMO_DATE = dt.date(2016, 10, 13)

# ----------------------------------------------------------------------------- farm / data
# 21 winter-cereal parcels (matches Farm map GeoJSON). Demo Today cases keep their soils.
# Clay/sand + day-13 RWC_eff are varied so classify_day yields a GO/CAUTION/NO-GO mix on the map.
_PARCELS = [
    # parcel_id, crop, area_ha, clay, sand, om, fc_mm, wp_mm
    ("PARCEL-0149869", "BARL", 7.61, 54.8, 15.0, 2.5, 131, 96),   # CAUTION (demo)
    ("PARCEL-0149906", "BARL", 6.34, 8.0, 77.6, 1.5, 38, 18),    # GO (demo)
    ("PARCEL-0149917", "BARL", 8.20, 39.2, 25.0, 2.2, 118, 80),  # CAUTION
    ("PARCEL-STUB-04", "COWT", 12.1, 12.0, 72.0, 1.6, 55, 22),   # GO sandy
    ("PARCEL-STUB-05", "COWT", 4.94, 18.0, 55.0, 1.8, 75, 35),   # GO
    ("PARCEL-STUB-06", "BARL", 9.20, 14.0, 68.0, 1.7, 60, 28),   # GO
    ("PARCEL-STUB-07", "BARL", 6.38, 16.0, 60.0, 1.9, 70, 32),   # GO
    ("PARCEL-STUB-08", "BARL", 7.66, 10.0, 75.0, 1.5, 48, 20),   # GO
    ("PARCEL-STUB-09", "COWT", 10.0, 28.0, 40.0, 2.1, 100, 58),  # CAUTION
    ("PARCEL-STUB-10", "BARL", 3.83, 35.0, 30.0, 2.3, 110, 70),  # CAUTION clay
    ("PARCEL-STUB-11", "COWT", 12.4, 25.0, 45.0, 2.0, 95, 52),   # CAUTION
    ("PARCEL-STUB-12", "BARL", 16.2, 32.0, 28.0, 2.4, 112, 68),  # CAUTION
    ("PARCEL-STUB-13", "BARL", 4.81, 22.0, 48.0, 2.0, 88, 45),   # CAUTION
    ("PARCEL-STUB-14", "COWT", 3.90, 40.0, 22.0, 2.5, 120, 82),  # CAUTION heavy
    ("PARCEL-STUB-15", "BARL", 6.46, 48.0, 18.0, 2.6, 128, 90),  # NO-GO wet clay
    ("PARCEL-STUB-16", "BARL", 3.17, 42.0, 20.0, 2.4, 122, 85),  # NO-GO
    ("PARCEL-STUB-17", "COWT", 5.74, 55.0, 12.0, 2.7, 135, 98),  # NO-GO
    ("PARCEL-STUB-18", "BARL", 10.7, 45.0, 16.0, 2.5, 125, 88),  # NO-GO
    ("PARCEL-STUB-19", "COWT", 4.82, 38.0, 25.0, 2.3, 115, 75),  # NO-GO
    ("PARCEL-STUB-20", "BARL", 5.35, 50.0, 14.0, 2.6, 130, 95),  # NO-GO
    ("PARCEL-STUB-21", "BARL", 17.7, 44.0, 18.0, 2.5, 124, 86),  # NO-GO
]


def load_farm(holding_id: str = "FARM-13525") -> pd.DataFrame:
    df = pd.DataFrame(_PARCELS, columns=["parcel_id", "crop", "area_ha", "clay_pct", "sand_pct",
                                         "om_pct", "fc_mm", "wp_mm"])
    score = (3 * df.crop.map(prm.PRIORITY["crop_sensitivity"].value)
             + 2 * df.clay_pct.map(lambda c: 3 if c >= 40 else 2 if c >= 25 else 1)
             + (df.area_ha >= prm.PRIORITY["area_min_ha"].value).astype(int))
    df["priority"] = score
    df["origin"] = "synthetic"
    return df


def farm_summary(holding_id: str = "FARM-13525") -> dict:
    """Extra (not in the contract): headline farm numbers for the Farm page."""
    return {"holding_id": holding_id, "nuts3": "PL415", "parcels": 51, "uaa_ha": 307.9, "awu": 4.89,
            "organic": False, "barley": {"parcels": 12, "ha": 78.2}, "wheat": {"parcels": 9, "ha": 55.6},
            "winter_cereals_ha": 133.7, "origin": "synthetic"}


def load_weather(nuts3: str = "PL415") -> pd.DataFrame:
    """Daily weather for Oct 2016 only (stub)."""
    dates = pd.date_range("2016-10-01", "2016-10-31")
    rain = dict.fromkeys(range(1, 32), 0.0)
    rain.update({3: 19.0, 5: 17.0, 6: 7.0, 11: 2.0, 12: 1.5, 20: 4.0, 24: 6.0})
    return pd.DataFrame({
        "date": dates, "precip_mm": [rain[d.day] for d in dates], "et0_mm": 1.2,
        "tmin_c": 5.0, "tmean_c": 9.0, "tmax_c": 13.0, "wind_m_s": 3.0, "origin": "real"})


# Day-13 RWC_eff for the Farm map mix (and Today demos). Other days keep the seasonal default.
_RWC_DAY13 = {
    "PARCEL-0149869": 1.00,   # CAUTION (demo M2)
    "PARCEL-0149906": 0.98,   # GO (demo M2; sand adj)
    "PARCEL-0149917": 0.97,   # CAUTION
    "PARCEL-STUB-04": 0.82,   # GO
    "PARCEL-STUB-05": 0.86,   # GO
    "PARCEL-STUB-06": 0.88,   # GO
    "PARCEL-STUB-07": 0.90,   # GO
    "PARCEL-STUB-08": 0.84,   # GO
    "PARCEL-STUB-09": 0.98,   # CAUTION
    "PARCEL-STUB-10": 0.96,   # CAUTION (clay adj)
    "PARCEL-STUB-11": 1.00,   # CAUTION
    "PARCEL-STUB-12": 0.97,   # CAUTION
    "PARCEL-STUB-13": 0.99,   # CAUTION
    "PARCEL-STUB-14": 0.98,   # CAUTION (clay adj → go 0.90 / caut 1.00)
    "PARCEL-STUB-15": 1.08,   # NO-GO
    "PARCEL-STUB-16": 1.10,   # NO-GO
    "PARCEL-STUB-17": 1.12,   # NO-GO
    "PARCEL-STUB-18": 1.09,   # NO-GO
    "PARCEL-STUB-19": 1.07,   # NO-GO
    "PARCEL-STUB-20": 1.11,   # NO-GO
    "PARCEL-STUB-21": 1.08,   # NO-GO
}


def _rwc_eff(parcel_id: str, d: dt.date) -> float:
    # Preserve 72-h strip drying for the two Today demo parcels.
    demo = {"PARCEL-0149869": {13: 1.00, 14: 0.94, 15: 0.90},
            "PARCEL-0149906": {13: 0.98, 14: 0.96, 15: 0.93}}.get(parcel_id, {})
    if d.day in demo:
        return demo[d.day]
    if d.day == 13 and parcel_id in _RWC_DAY13:
        return _RWC_DAY13[parcel_id]
    return 1.04 if d.day <= 12 else 0.97


def soil_water(parcels: pd.DataFrame | None = None, weather: pd.DataFrame | None = None) -> pd.DataFrame:
    parcels = load_farm() if parcels is None else parcels
    weather = load_weather() if weather is None else weather
    w = weather.reset_index(drop=True).copy()
    w["prev24"] = w.precip_mm.shift(1).fillna(0.0)
    w["prev48"] = w.precip_mm.rolling(2, min_periods=1).sum().shift(1).fillna(0.0)
    rows = []
    for pid, fc, wp in zip(parcels.parcel_id, parcels.fc_mm, parcels.wp_mm):
        for _, r in w.iterrows():
            d = r.date.date()
            rwc = min(1.0, _rwc_eff(pid, d))
            rows.append((pid, r.date, wp + rwc * (fc - wp), rwc, _rwc_eff(pid, d), r.precip_mm,
                         r.prev24, r.prev48, r.tmax_c, "modelled"))
    return pd.DataFrame(rows, columns=["parcel_id", "date", "W_mm", "RWC", "RWC_eff", "rain_today_mm",
                                       "rain_prev24h_mm", "rain_prev48h_mm", "tmax_c", "origin"])


# ----------------------------------------------------------------------------- status (Mirela)
def axle_load_class(machine_id: str, load_pct: float) -> tuple[str, float]:
    m = prm.MACHINES[machine_id]
    loaded = m["max_axle_t"].value
    axle = loaded * (m["empty_share"].value + (1 - m["empty_share"].value) * load_pct / 100.0)
    if load_pct >= 100:   # spec 6.1 table lists the class at full load; its bounds disagree for M3 (8 t) and M6 (10 t)
        return m["load_class"], round(axle, 2)
    for cls, p in prm.LOAD_CLASS_BOUNDS.items():
        lo, hi = p.value
        if lo < axle <= hi:   # upper bound inclusive so that 8 t = L3
            return cls, round(axle, 2)
    return "L1", round(axle, 2)


_RANK = {"GO": 0, "CAUTION": 1, "NO-GO": 2}


def _worse(a: str, b: str) -> str:
    return a if _RANK[a] >= _RANK[b] else b


def classify_day(rwc_eff, clay_pct, sand_pct, rain_today_mm, rain_prev24h_mm, tmax_c, load_class,
                 passes=1, operation="sowing") -> dict:
    """Crude stand-in for Mirela's classify_day (same output keys)."""
    t = prm.THRESHOLDS[load_class]
    adj = 0.0
    if clay_pct >= prm.TEXTURE_ADJUSTMENT["clay_min_pct"].value:
        adj += prm.TEXTURE_ADJUSTMENT["clay_delta"].value
    if sand_pct >= prm.TEXTURE_ADJUSTMENT["sand_min_pct"].value:
        adj += prm.TEXTURE_ADJUSTMENT["sand_delta"].value
    adj += (passes - 1) * prm.PASSES["threshold_delta_per_extra_pass"].value
    go, caution = t["go"].value + adj, t["caution"].value + adj
    status = "GO" if rwc_eff <= go else "CAUTION" if rwc_eff <= caution else "NO-GO"
    reasons = [f"Soil water RWC_eff {rwc_eff:.2f} vs GO <= {go:.2f}, CAUTION <= {caution:.2f} ({load_class})"]
    if rain_today_mm >= prm.RAIN_OVERRIDES["rain_today_nogo_mm"].value:
        status, reasons = "NO-GO", reasons + [f"Rain today {rain_today_mm:.0f} mm"]
    if rain_prev24h_mm >= prm.RAIN_OVERRIDES["rain_prev24h_caution_mm"].value:
        status = _worse(status, "CAUTION")
        reasons.append(f"Rain in previous 24 h {rain_prev24h_mm:.0f} mm")
    suitability = "GO" if rain_today_mm < 1 or operation != "sowing" else "CAUTION"
    return {"status": status, "access": status, "suitability": suitability,
            "risk": {"GO": 15, "CAUTION": 50, "NO-GO": 85}[status], "reasons": reasons, "origin": "modelled"}


def status_table(soil_water_df: pd.DataFrame, parcels: pd.DataFrame, load_class: str, passes: int = 1,
                 operation: str = "sowing") -> pd.DataFrame:
    tex = parcels.set_index("parcel_id")[["clay_pct", "sand_pct"]]
    out = soil_water_df.copy()
    res = [classify_day(r.RWC_eff, tex.at[r.parcel_id, "clay_pct"], tex.at[r.parcel_id, "sand_pct"],
                        r.rain_today_mm, r.rain_prev24h_mm, r.tmax_c, load_class, passes, operation)
           for r in out.itertuples()]
    out["status"] = [r["status"] for r in res]
    out["risk"] = [r["risk"] for r in res]
    out["reasons"] = [r["reasons"] for r in res]
    return out


# ----------------------------------------------------------------------------- season (Marek)
_COMPLETION = {   # extra contractor ha/day -> completion date (day of Oct, Oct 2015..2024); 22 -> 22 Oct
    0: [9, 22, 16, 9, 16, 16, 10, 9, 13, 11],
    5: [8, 19, 14, 8, 14, 14, 9, 8, 12, 10],
    10: [7, 15, 13, 7, 13, 13, 8, 7, 11, 9],
    15: [6, 13, 11, 6, 11, 11, 7, 6, 10, 8],
}


def season(params: dict | None = None, skip_dates=None, years=None, perfect_weather: bool = False) -> dict:
    params = params or {}
    extra = max(k for k in _COMPLETION if k <= params.get("contractor_ha_day", 0))
    days = [9] * 10 if perfect_weather else _COMPLETION[extra]
    yrs = [y for y in YEARS if years is None or y in years]
    comp = pd.DataFrame({"year": YEARS, "completion_date": [dt.date(y, 10, d) for y, d in zip(YEARS, days)]})
    comp = comp[comp.year.isin(yrs)].reset_index(drop=True)
    deadline = lambda y: dt.date(y, 10, 15)  # noqa: E731 (stub only; real one reads params)
    p = float(np.mean([c <= deadline(y) for y, c in zip(comp.year, comp.completion_date)]))
    comp["origin"] = "modelled"
    farm = load_farm()
    sched = [(r.parcel_id, y, c - dt.timedelta(days=i), r.area_ha, c)
             for y, c in zip(comp.year, comp.completion_date) for i, r in enumerate(farm.itertuples())]
    schedule = pd.DataFrame(sched, columns=["parcel_id", "year", "date", "ha_done", "completion_date"])
    schedule["origin"] = "modelled"
    order = farm.sort_values("priority", ascending=False)
    rng = np.random.RandomState(0)
    wd = [(y, dt.date(y, 10, d), float(0.6 if y == 2016 and d in (1, 2, 13) else rng.uniform(0, 0.5)))
          for y in YEARS for d in range(1, 32)]
    return {
        "P_by_deadline": {"value": p, "unit": "share", "origin": "modelled"},
        "completion": comp,
        "schedule": schedule,
        "parcel_order": [{"parcel_id": r.parcel_id, "priority": int(r.priority),
                          "reason": "heavy soil first" if r.clay_pct >= 40 else "lighter soil later",
                          "origin": "assumption"} for r in order.itertuples()],
        "contractor_recommendation": {"extra_ha_day": 5, "ha": 35, "start": "1 Oct", "p_with": 0.9,
                                      "origin": "modelled"},
        "sensitivity": {0.0: 0.6, 0.5: 0.6, 1.0: 1.0, "origin": "modelled"},
        "workable_days": pd.DataFrame(wd, columns=["year", "date", "share_go"]).assign(origin="modelled"),
    }


# ----------------------------------------------------------------------------- cost (Mirela)
_WEATHER_DEFAULT = [1400, 10700, 3900, 1400, 3900, 3900, 1200, 1400, 2800, 2400]
_RATE_X = {"low": 0.5, "default": 1.0, "high": 1.5}
_LATE_START_DEFAULT = 18000


def season_cost(schedule=None, parcels=None, params: dict | None = None) -> dict:
    rows = []
    for y, w in zip(YEARS, _WEATHER_DEFAULT):
        r = {"year": y}
        for rate, x in _RATE_X.items():
            r[f"weather_{rate}"] = w * x
            r[f"late_start_{rate}"] = _LATE_START_DEFAULT * x
            r[f"total_{rate}"] = (w + _LATE_START_DEFAULT) * x
        rows.append(r)
    per_year = pd.DataFrame(rows).assign(origin="real+synthetic+assumption")
    med = {c: float(per_year[c].median()) for c in per_year.columns if c.startswith(("weather_", "late_start_", "total_"))}
    return {"per_year": per_year, "median": med, "worst_year": {"year": 2016, "weather_default": 10700.0,
            "weather_low": 5350.0, "weather_high": 16050.0}, "unit": "EUR",
            "origin": "real+synthetic+assumption"}


def contractor_value(cost_without: dict | None = None, cost_with: dict | None = None,
                     contractor_ha: float | None = 60, contractor_price: float | None = 68) -> dict:
    out = {"value_median": 5500.0, "value_worst": 10500.0, "worst_year": 2016, "unit": "EUR",
           "origin": "real+synthetic+assumption"}
    if contractor_price is None or contractor_ha is None:
        out.update(net_benefit_median=NA, net_benefit_worst=NA)
    else:
        fee = contractor_ha * contractor_price
        out.update(contractor_fee=fee, net_benefit_median=5500.0 - fee, net_benefit_worst=10500.0 - fee)
    return out


def wait_cost(date, params: dict | None = None) -> dict:
    d = pd.Timestamp(date).date()
    eur = {dt.date(2016, 10, 13): 1700.0, dt.date(2016, 10, 17): 1400.0}.get(d, NA)
    return {"eur": eur, "unit": "EUR", "days_to_first_go": 1 if eur != NA else NA,
            "origin": "real+synthetic+assumption"}


# ----------------------------------------------------------------------------- today (Marek)
def today(parcel_id: str, date, machine_id: str = "M2", load_pct: float = 100, passes: int = 1,
          operation: str = "sowing") -> dict:
    d = pd.Timestamp(date).date()
    farm = load_farm().set_index("parcel_id")
    sw = soil_water()
    wx = load_weather()
    cls, axle = axle_load_class(machine_id, load_pct)
    pr = farm.loc[parcel_id]
    strip = []
    for k in range(3):
        dd = d + dt.timedelta(days=k)
        row = sw[(sw.parcel_id == parcel_id) & (sw.date == pd.Timestamp(dd))]
        if row.empty:
            strip.append({"date": dd, "status": NA})
            continue
        r = row.iloc[0]
        c = classify_day(r.RWC_eff, pr.clay_pct, pr.sand_pct, r.rain_today_mm, r.rain_prev24h_mm,
                         r.tmax_c, cls, passes, operation)
        strip.append({"date": dd, "status": c["status"]})
    row = sw[(sw.parcel_id == parcel_id) & (sw.date == pd.Timestamp(d))]
    wxr = wx[wx.date == pd.Timestamp(d)]
    if row.empty or wxr.empty:
        return {"status": NA, "access": NA, "suitability": NA, "strip72": strip, "reasons": ["Stub covers Oct 2016 only"],
                "confidence": NA, "based_on": [], "missing": ["stub data for this date"],
                "best_next_check": NA, "conditions": {}, "load_class": cls, "axle_load_t": axle, "origin": "modelled"}
    r, w = row.iloc[0], wxr.iloc[0]
    c = classify_day(r.RWC_eff, pr.clay_pct, pr.sand_pct, r.rain_today_mm, r.rain_prev24h_mm, r.tmax_c,
                     cls, passes, operation)
    cf = prm.CONFIDENCE
    confidence = sum(cf[k].value for k in ("start", "weather_regional", "soil_synthetic", "default_machine",
                                           "replay_not_forecast", "no_farmer_observation"))
    return {
        "status": _worse(c["access"], c["suitability"]), "access": c["access"], "suitability": c["suitability"],
        "strip72": strip, "reasons": c["reasons"], "confidence": confidence,
        "based_on": ["AgERA5 regional weather (replay)", "Synthetic parcel soil", f"Machine profile {machine_id}"],
        "missing": ["Field-level weather", "Soil-moisture reading", "Farmer observation"],
        "best_next_check": "Ball/ribbon hand test on the wettest part of the field (or a soil-moisture reading at 20 cm)",
        "conditions": {"rwc_eff": round(float(r.RWC_eff), 2), "precip_mm": float(w.precip_mm),
                       "precip_last48h_mm": float(r.rain_prev48h_mm), "tmin_c": float(w.tmin_c),
                       "tmax_c": float(w.tmax_c), "wind_m_s": float(w.wind_m_s)},
        "load_class": cls, "axle_load_t": axle, "origin": "modelled",
    }


def safer_plan(parcel_id: str, date, machine_id: str = "M3", load_pct: float = 100, passes: int = 1) -> list[dict]:
    return [
        {"lever": "other parcel today", "parcel_id": "PARCEL-0149906", "date": pd.Timestamp(date).date(),
         "load_pct": load_pct, "status": "GO", "reason": "Light sandy soil drains faster (sand 77.6%)",
         "cost": {"eur": 0.0, "origin": "real+synthetic+assumption"}},
        {"lever": "lighter load", "parcel_id": parcel_id, "date": pd.Timestamp(date).date(),
         "load_pct": 40, "status": "CAUTION", "reason": "Lower axle load class on the same parcel",
         "cost": {"eur": 400.0, "origin": "real+synthetic+assumption"}},
        {"lever": "other day", "parcel_id": parcel_id, "date": pd.Timestamp(date).date() + dt.timedelta(days=1),
         "load_pct": load_pct, "status": "CAUTION", "reason": "Topsoil drier tomorrow, still above GO threshold",
         "cost": {"eur": 1700.0, "origin": "real+synthetic+assumption"}},
    ]


def make_record(today_result: dict, parcel_id: str, operation: str = "sowing", overridden: bool = False) -> dict:
    return {"record_id": "REC-STUB-001", "parcel_id": parcel_id, "operation": operation,
            "date": dt.date(2016, 10, 13), "status_at_decision": today_result.get("status"),
            "overridden": overridden, "conditions": today_result.get("conditions", {}),
            "confidence": today_result.get("confidence"), "origin": "modelled"}


# ----------------------------------------------------------------------------- records (Marek)
def lint_records(holding_id: str = "FARM-13525", campaign: int | None = 2024) -> dict:
    if holding_id == prm.DEMO["organic_holding_id"].value:
        cards = [{"rule": "R2", "title": "Mineral fertiliser on an organic holding", "n_rows": 1316,
                  "why": "Organic certification forbids mineral fertiliser.",
                  "fix": "Check the holding's organic status or the product type of these records.",
                  "rows": pd.DataFrame({"parcel_id": ["PARCEL-STUB"], "app_date": ["2024-03-02"]})}]
        n_rec, n_flags = 1316, 1316
    else:
        mk = lambda rule, title, n, why, fix: {"rule": rule, "title": title, "n_rows": n, "why": why,  # noqa: E731
                                               "fix": fix, "rows": pd.DataFrame({"parcel_id": ["PARCEL-STUB"], "detail": [title]})}
        cards = [
            mk("R5", "All fertiliser rows repeat the same rate", 85, "Identical N/P values in every row of a parcel-year look like a copy error.", "Confirm whether the rate is per event or per year."),
            mk("R4", "Fertigation on a parcel with no irrigation that year", 18, "Fertigation needs irrigation water.", "Fix the method or the irrigation record."),
            mk("R3", "Nitrogen applied in the closed period (Dec-Jan)", 13, "Closed period for mineral N (verify per country).", "Check the application date."),
            mk("R1", "Sprays dated after the maize harvest", 12, "A spray after harvest cannot be on the crop.", "Check the date or the parcel."),
        ]
        n_rec, n_flags = 177, 143
    flags = pd.DataFrame({"rule": [c["rule"] for c in cards], "n_rows": [c["n_rows"] for c in cards]})
    return {"cards": cards, "flags": flags, "n_records": n_rec, "n_flags": n_flags, "origin": "synthetic"}
