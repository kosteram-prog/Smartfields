"""Today assessment "FieldGo Quick Check" (owner: Marek). Spec 7.7 and 7.9.

Can this machine, with this load, go on this parcel today? Field access comes from the day-status rules
(Mirela's engine.status.classify_day; the stub until it exists). Operation suitability (no rain for sowing,
no frozen soil for fertilising, no wind/rain for spraying) is checked here. Overall = the worse of the two.

  assess(soil_water, weather, parcel, date, machine_id, load_pct, passes, operation) -> dict  (pure)
  today(parcel_id, date, machine_id, load_pct, passes, operation)                    -> dict  (contract)
"""
from __future__ import annotations

from functools import lru_cache

import pandas as pd

from engine import params as prm

NA = "not available"
RANK = {"GO": 0, "CAUTION": 1, "NO-GO": 2}
BEST_NEXT_CHECK = ("Ball/ribbon hand test (AHDB) on the wettest part of the field: if the soil moulds into a ball "
                   "or ribbon, it is plastic, so wait. Option: a soil-moisture reading at 20 cm.")


def _worse(*statuses: str) -> str:
    return max(statuses, key=lambda s: RANK.get(s, -1))


def _status_fns():
    try:
        from engine import status as st_mod
        if hasattr(st_mod, "classify_day") and hasattr(st_mod, "axle_load_class"):
            return st_mod.classify_day, st_mod.axle_load_class, "engine.status"
    except ImportError:
        pass
    from engine import stubs
    return stubs.classify_day, stubs.axle_load_class, "stub (engine/stubs.py)"


def suitability(operation: str, rain_today_mm: float, tmax_c: float, wind_m_s: float) -> tuple[str, list[str]]:
    """Can the operation itself be done well today (independent of whether the machine can enter)?"""
    s, reasons = "GO", []
    su = prm.SUITABILITY
    if operation == "sowing" and rain_today_mm >= su["sowing_rain_caution_mm"].value:
        s = "CAUTION"
        reasons.append(f"Rain today {rain_today_mm:.1f} mm: poor sowing conditions (seed-bed smearing)")
    if operation == "fertilising" and tmax_c <= prm.FROST["tmax_c"].value:
        s = "NO-GO"
        reasons.append(f"Frozen soil (Tmax {tmax_c:.1f} °C): no fertilising")
    if operation == "spraying":
        if rain_today_mm >= su["spray_rain_caution_mm"].value:
            s = _worse(s, "CAUTION")
            reasons.append(f"Rain today {rain_today_mm:.1f} mm: risk of wash-off")
        if wind_m_s >= su["spray_wind_caution_m_s"].value:
            s = _worse(s, "CAUTION")
            reasons.append(f"Mean wind {wind_m_s:.1f} m/s: drift risk")
    return s, reasons


def confidence(load_pct, passes, observation, custom_machine: bool = False) -> tuple[int, list[str], list[str]]:
    """Spec 7.9: start at 100 and subtract per missing or indirect input. Returns (score, based_on, missing)."""
    c = prm.CONFIDENCE
    score = c["start"].value + c["weather_regional"].value + c["soil_synthetic"].value + c["replay_not_forecast"].value
    based_on = ["AgERA5 weather, regional average (replay of history, not a forecast)",
                "Parcel soil texture (synthetic) -> Saxton-Rawls soil-water model, 0-30 cm"]
    missing = ["Field-level weather", "Measured soil moisture"]
    if custom_machine:
        based_on.append("Your machine data")
    else:
        score += c["default_machine"].value
        based_on.append("Default machine profile (spec 6.1)")
        missing.append("Your own machine data (axle load)")
    if load_pct is None:
        score += c["missing_load"].value
        missing.append("Load of the machine")
    if passes is None:
        score += c["missing_passes"].value
        missing.append("Number of passes")
    if observation:
        based_on.append(f"Farmer observation: {observation}")
    else:
        score += c["no_farmer_observation"].value
        missing.append("Farmer observation (hand test)")
    return int(score), based_on, missing


def quality_label(score) -> str:
    if not isinstance(score, (int, float)):
        return NA
    lv = prm.CONFIDENCE_LEVELS
    return "high" if score >= lv["high_min"].value else "medium" if score >= lv["medium_min"].value else "low"


def assess(soil_water: pd.DataFrame, weather: pd.DataFrame, parcel: pd.Series, date, machine_id: str,
           load_pct, passes, operation: str = "sowing", observation: str | None = None,
           custom_machine: dict | None = None) -> dict:
    """Pure Today assessment from the parcel's soil-water table and the regional weather.

    custom_machine: {"name": str, "axle_t": max axle load in t at the current load} (spec 6.1 custom form).
    """
    classify_day, axle_load_class, source = _status_fns()
    d = pd.Timestamp(date)
    if custom_machine and custom_machine.get("axle_t"):
        from engine.status import load_class_for_axle
        axle = float(custom_machine["axle_t"])
        lc = load_class_for_axle(axle)
        machine_id = custom_machine.get("name") or "custom machine"
    else:
        lc, axle = axle_load_class(machine_id, 100 if load_pct is None else load_pct)
    n_pass = 1 if passes is None else int(passes)
    sw = soil_water.set_index(pd.to_datetime(soil_water["date"]))
    wx = weather.set_index(pd.to_datetime(weather["date"]))

    def day(dd):
        if dd not in sw.index or dd not in wx.index:
            return None
        r, w = sw.loc[dd], wx.loc[dd]
        c = classify_day(float(r.RWC_eff), float(parcel.clay_pct), float(parcel.sand_pct), float(r.rain_today_mm),
                         float(r.rain_prev24h_mm), float(r.tmax_c), lc, n_pass, operation)
        s_suit, suit_reasons = suitability(operation, float(r.rain_today_mm), float(w.tmax_c), float(w.wind_m_s))
        s_suit = _worse(s_suit, c.get("suitability", "GO"))         # respect Mirela's suitability rule too
        return {"access": c["access"], "suitability": s_suit, "status": _worse(c["access"], s_suit),
                "reasons": list(c["reasons"]) + suit_reasons, "risk": c.get("risk"), "r": r, "w": w}

    strip, first_go = [], "beyond 72 h"
    for k in range(3):
        dd = d + pd.Timedelta(days=k)
        res = day(dd)
        strip.append({"date": dd, "status": res["status"] if res else NA, "origin": "real+modelled"})
        if res and res["status"] == "GO" and first_go == "beyond 72 h":
            first_go = k

    now = day(d)
    if now is None:
        return {"status": NA, "access": NA, "suitability": NA, "strip72": strip, "days_to_first_go": NA,
                "reasons": [f"No weather or soil-water data for {d:%d %b %Y}"], "confidence": NA,
                "data_quality": NA, "based_on": [], "missing": ["Weather for this date"],
                "best_next_check": BEST_NEXT_CHECK, "conditions": {}, "load_class": lc, "axle_load_t": axle,
                "status_source": source, "origin": "modelled"}
    score, based_on, missing = confidence(load_pct, passes, observation, custom_machine=bool(custom_machine))
    if n_pass > 1:
        now["reasons"].append(f"{n_pass} passes on the same day: thresholds stricter by "
                              f"{abs(prm.PASSES['threshold_delta_per_extra_pass'].value) * (n_pass - 1):.2f}")
    r, w = now["r"], now["w"]
    return {
        "status": now["status"], "access": now["access"], "suitability": now["suitability"], "risk": now["risk"],
        "strip72": strip, "days_to_first_go": first_go, "reasons": now["reasons"],
        "confidence": score, "data_quality": quality_label(score), "based_on": based_on, "missing": missing,
        "best_next_check": BEST_NEXT_CHECK,
        "conditions": {"rwc_eff": float(r.RWC_eff), "precip_mm": float(w.precip_mm),
                       "precip_last48h_mm": float(r.rain_prev48h_mm), "tmin_c": float(w.tmin_c),
                       "tmax_c": float(w.tmax_c), "wind_m_s": float(w.wind_m_s)},
        "conditions_origin": {"rwc_eff": "modelled", "weather": "real"},
        "load_class": lc, "axle_load_t": axle, "machine_id": machine_id, "parcel_id": parcel.parcel_id,
        "load_pct": load_pct, "passes": passes, "crop": parcel.get("crop"), "area_ha": parcel.get("area_ha"),
        "date": d, "operation": operation, "status_source": source, "origin": "modelled",
    }


# --------------------------------------------------------------------------- contract function (loads data)
@lru_cache(maxsize=8)
def _farm_inputs(data_dir: str, holding_id: str, nuts3: str):
    from engine import data, soil
    farm = data.load_farm(holding_id)
    wx = data.load_weather(nuts3)
    return farm, wx, soil.soil_water(farm, wx)


def today(parcel_id: str, date, machine_id: str = "M2", load_pct=100, passes=1, operation: str = "sowing",
          observation: str | None = None, holding_id: str | None = None, custom_machine: dict | None = None) -> dict:
    import config
    holding_id = holding_id or prm.DEMO["holding_id"].value
    farm, wx, sw = _farm_inputs(str(config.get_data_dir()), holding_id, prm.DEMO["nuts3"].value)
    hit = farm[farm.parcel_id == parcel_id]
    if hit.empty:
        raise ValueError(f"Parcel {parcel_id} is not on holding {holding_id}")
    return assess(sw[sw.parcel_id == parcel_id], wx, hit.iloc[0], date, machine_id, load_pct, passes, operation,
                  observation=observation, custom_machine=custom_machine)
