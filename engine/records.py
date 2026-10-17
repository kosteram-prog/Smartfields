"""Record creation for "Mark as done" (spec 7.11) and the BBCH estimate (spec 6.6, 7.12).

Written by Marek's agent for Mirela's slice (agreed 16 Oct 20:22); Mirela reviews.
"""
from __future__ import annotations

import uuid

import pandas as pd

from engine import params as prm

NA = "not available"
WINTER_CEREALS = ("COWT", "BARL")
MANDATORY_PPP = ("product_name", "dose", "dose_unit")      # Implementing Regulation (EU) 2023/564 (subset)
RECORD_FIELDS = ["record_id", "holding_id", "parcel_id", "date", "operation", "crop", "crop_eppo", "product_name",
                 "dose", "dose_unit", "area_ha", "bbch_estimated", "bbch_source", "machine_id", "load_pct", "passes",
                 "decision_status", "overridden", "rwc_eff", "precip_mm", "precip_last48h_mm", "tmin_c", "tmax_c",
                 "wind_m_s", "weather_source", "created_at"]


def bbch_from_thermal_time(tt: float) -> int:
    stages = prm.BBCH["thermal_time"].value                  # {bbch: degree-days}
    return max(b for b, need in stages.items() if tt >= need)


def bbch_estimate(crop: str, sowing_date, date, weather: pd.DataFrame | None) -> tuple:
    """(bbch, source). Winter cereals: thermal time since sowing, base 0 °C; other crops: manual."""
    if crop not in WINTER_CEREALS:
        return NA, "manual (BBCH estimate only for winter cereals)"
    d, s = pd.Timestamp(date), pd.Timestamp(sowing_date) if sowing_date is not None else None
    if s is None or pd.isna(s) or d < s:
        return NA, "manual (no sowing date)"
    if d == s:
        return 0, "estimated: sowing day"
    w = weather.set_index(pd.to_datetime(weather["date"])).loc[s:d, "tmean_c"]
    if w.isna().any() or len(w) < (d - s).days + 1:
        return NA, "manual (weather missing)"
    tt = float((w - prm.BBCH["base_temp_c"].value).clip(lower=0).sum())
    return bbch_from_thermal_time(tt), f"estimated: {tt:.0f} °Cd since sowing (prototype)"


def _r(x, n):
    """Round a number for the record (None and 'not available' stay as they are)."""
    return round(float(x), n) if isinstance(x, (int, float)) and x == x else x


def make_record(today_result: dict, parcel_id: str, operation: str = "sowing", overridden: bool = False,
                product_name: str | None = None, dose=None, dose_unit: str | None = None) -> dict:
    from engine import data
    holding = prm.DEMO["holding_id"].value
    farm = data.load_farm(holding).set_index("parcel_id")
    p = farm.loc[parcel_id]
    d = pd.Timestamp(today_result.get("date"))
    crop = p["crop"]
    if operation == "sowing":
        sowing = d
    else:
        pl = data.load_operations("planting", holding)
        pl = pl[(pl.parcel_id == parcel_id) & (pl.plant_date <= d)]
        sowing = pl.plant_date.max() if len(pl) else None
    bbch, src = bbch_estimate(crop, sowing, d, data.load_weather(p["nuts3"]))
    cond = today_result.get("conditions") or {}
    rec = {
        "record_id": f"REC-{uuid.uuid4().hex[:8].upper()}", "holding_id": holding, "parcel_id": parcel_id,
        "date": d.date().isoformat(), "operation": operation, "crop": crop,
        "crop_eppo": prm.EPPO_CODES.value.get(crop, NA), "product_name": product_name or "", "dose": dose,
        "dose_unit": dose_unit or "", "area_ha": round(float(p["area_ha"]), 2), "bbch_estimated": bbch, "bbch_source": src,
        "machine_id": today_result.get("machine_id"), "load_pct": today_result.get("load_pct"),
        "passes": today_result.get("passes"), "decision_status": today_result.get("status"),
        "overridden": bool(overridden), "rwc_eff": _r(cond.get("rwc_eff"), 2), "precip_mm": _r(cond.get("precip_mm"), 1),
        "precip_last48h_mm": _r(cond.get("precip_last48h_mm"), 1), "tmin_c": _r(cond.get("tmin_c"), 1),
        "tmax_c": _r(cond.get("tmax_c"), 1), "wind_m_s": _r(cond.get("wind_m_s"), 1),
        "weather_source": "AgERA5 regional (replay)", "created_at": pd.Timestamp.utcnow().isoformat(timespec="seconds"),
    }
    needs_product = operation in ("spraying", "fertilising")
    rec["missing_fields"] = [f for f in MANDATORY_PPP if needs_product and not rec[f]]
    rec["origin"] = "modelled+real+synthetic"
    return rec
