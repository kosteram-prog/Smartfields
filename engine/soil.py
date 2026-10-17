"""Soil hydraulics (Saxton & Rawls 2006) and the daily 0-30 cm soil-water bucket (owner: Marek).

Spec 6.3 and 7.2. Pure functions, all parameters from engine/params.py.
  saxton_rawls(sand_pct, clay_pct, om_pct) -> (theta_wp, theta_33) in m3/m3 (1500 and 33 kPa)
  saturation(sand_pct, clay_pct, om_pct)   -> theta_S (m3/m3)
  field_capacity(sand, clay, om, kpa)      -> theta at params SAXTON_RAWLS['fc_kpa'] (10 kPa since 17 Oct)
  add_hydraulics(parcels)                  -> parcels + fc_mm, wp_mm, taw_mm for the bucket layer
  soil_water(parcels, weather, evaporation) -> daily W, RWC, RWC_eff per parcel (contract table)
  fao56_tew_rew(parcels)                   -> TEW and REW (mm) for the FAO-56 evaporation option
Missing texture gives NaN ('not available'), never 0.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from engine import params as prm

ORIGIN = "modelled"


def saxton_rawls(sand_pct, clay_pct, om_pct):
    """Wilting point (1500 kPa) and field capacity (33 kPa) as volumetric fractions.

    Inputs: sand and clay in %, organic matter in % by weight (arrays or scalars).
    Equations 1-4 of Saxton & Rawls (2006, SSSAJ 70:1569), coefficients in params.SAXTON_RAWLS.
    """
    S = np.asarray(sand_pct, dtype=float) / 100.0
    C = np.asarray(clay_pct, dtype=float) / 100.0
    OM = np.asarray(om_pct, dtype=float)
    a = prm.SAXTON_RAWLS["theta1500t"].value
    t1500t = (a["S"] * S + a["C"] * C + a["OM"] * OM + a["S_OM"] * S * OM
              + a["C_OM"] * C * OM + a["S_C"] * S * C + a["const"])
    adj = prm.SAXTON_RAWLS["theta1500_adj"].value
    wp = t1500t + (adj["a"] * t1500t + adj["b"])
    b = prm.SAXTON_RAWLS["theta33t"].value
    t33t = (b["S"] * S + b["C"] * C + b["OM"] * OM + b["S_OM"] * S * OM
            + b["C_OM"] * C * OM + b["S_C"] * S * C + b["const"])
    adj = prm.SAXTON_RAWLS["theta33_adj"].value
    fc = t33t + (adj["a"] * t33t ** 2 + adj["b"] * t33t + adj["c"])
    return wp, fc


def _terms(sand_pct, clay_pct, om_pct):
    S = np.asarray(sand_pct, dtype=float) / 100.0
    C = np.asarray(clay_pct, dtype=float) / 100.0
    OM = np.asarray(om_pct, dtype=float)
    return S, C, OM


def saturation(sand_pct, clay_pct, om_pct):
    """Saturated water content theta_S (Saxton & Rawls 2006 eq. 2, 3, 5), m3/m3."""
    S, C, OM = _terms(sand_pct, clay_pct, om_pct)
    a = prm.SAXTON_RAWLS["thetaS33t"].value
    t = (a["S"] * S + a["C"] * C + a["OM"] * OM + a["S_OM"] * S * OM + a["C_OM"] * C * OM + a["S_C"] * S * C
         + a["const"])
    adj = prm.SAXTON_RAWLS["thetaS33_adj"].value
    ts33 = t + (adj["a"] * t + adj["b"])
    _, t33 = saxton_rawls(sand_pct, clay_pct, om_pct)
    sa = prm.SAXTON_RAWLS["thetaS_sand"].value
    return t33 + ts33 + sa["a"] * S + sa["b"]


def field_capacity(sand_pct, clay_pct, om_pct, kpa: float | None = None):
    """Water content at the field-capacity suction (default params SAXTON_RAWLS['fc_kpa'], 10 kPa).

    S&R power law psi = A theta^-B through 33 and 1500 kPa: theta(kpa) = theta33 * (33 / kpa)^(1/B),
    B = ln(1500/33) / ln(theta33/theta1500); capped at saturation. kpa = 33 gives S&R theta33.
    """
    kpa = prm.SAXTON_RAWLS["fc_kpa"].value if kpa is None else kpa
    wp, t33 = saxton_rawls(sand_pct, clay_pct, om_pct)
    if kpa == 33:
        return t33
    with np.errstate(invalid="ignore", divide="ignore"):
        b = np.log(1500.0 / 33.0) / np.log(t33 / wp)
        theta = t33 * (33.0 / kpa) ** (1.0 / b)
    return np.minimum(theta, saturation(sand_pct, clay_pct, om_pct))


def add_hydraulics(parcels: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of the parcels table with fc_mm (at params fc_kpa), wp_mm and taw_mm (mm in the bucket layer)."""
    out = parcels.copy()
    depth = prm.BUCKET["layer_depth_mm"].value
    wp, _ = saxton_rawls(out["sand_pct"], out["clay_pct"], out["om_pct"])
    fc = field_capacity(out["sand_pct"], out["clay_pct"], out["om_pct"])
    out["wp_mm"] = np.asarray(wp, dtype=float) * depth
    out["fc_mm"] = np.asarray(fc, dtype=float) * depth
    out["taw_mm"] = out["fc_mm"] - out["wp_mm"]
    return out


def fao56_tew_rew(parcels: pd.DataFrame):
    """FAO-56 readily and total evaporable water (mm) per parcel: TEW = 1000 (theta_FC - 0.5 theta_WP) Ze."""
    depth = prm.BUCKET["layer_depth_mm"].value
    ze = prm.FAO56["ze_m"].value
    th_fc = parcels["fc_mm"].to_numpy(dtype=float) / depth
    th_wp = parcels["wp_mm"].to_numpy(dtype=float) / depth
    tew = 1000.0 * (th_fc - 0.5 * th_wp) * ze
    sand = parcels["sand_pct"].to_numpy(dtype=float)
    clay = parcels["clay_pct"].to_numpy(dtype=float)
    rew = np.full(len(parcels), np.nan)
    for kind, lim, val in prm.FAO56["rew_mm"].value:
        hit = np.isnan(rew) & ((kind == "else") | ((kind == "sand_min") & (sand >= (lim or 0)))
                               | ((kind == "clay_min") & (clay >= (lim or 0))))
        rew[hit] = val
    return tew, np.minimum(rew, 0.8 * tew)


def _clean_weather(weather: pd.DataFrame) -> pd.DataFrame:
    need = ["date", "precip_mm", "et0_mm", "tmax_c"]
    missing = [c for c in need if c not in weather.columns]
    if missing:
        raise ValueError(f"weather is missing columns: {missing}")
    w = weather.sort_values("date").reset_index(drop=True)
    w["date"] = pd.to_datetime(w["date"])
    w = w[w["date"] >= pd.Timestamp(prm.BUCKET["initial_date"].value)].reset_index(drop=True)
    if w.empty:
        raise ValueError("weather has no days on or after the bucket start date")
    if not (w["date"].diff().dropna() == pd.Timedelta(days=1)).all():
        raise ValueError("weather must have one row per day without gaps or duplicates")
    if w[["precip_mm", "et0_mm"]].isna().any().any():
        raise ValueError("weather has missing precipitation or ET0 values (not guessing)")
    return w


def soil_water(parcels: pd.DataFrame, weather: pd.DataFrame, evaporation: str | None = None) -> pd.DataFrame:
    """Daily soil-water bucket for every parcel (vectorised across parcels, sequential in time).

    Day t: ETa = ET0 * beta, beta = clip((W - WP) / (0.5 * TAW), 0, 1) from the water at the start of the day;
    W <- W + P - ETa; excess above FC drains (W = FC), flag saturated_today if P >= 10 mm; W >= WP.
    RWC = (W - WP) / (FC - WP); RWC_eff = RWC + k * min(1, P_48h / 20 mm) (wetness above FC, prototype).
    P_48h = rain today + rain yesterday (this window reproduces the pre-event test table for Oct 2016;
    a window of the two previous days does not). rain_prev24h_mm = yesterday only.
    The bucket starts full (W = FC) on the first weather day on or after params.BUCKET['initial_date'].
    evaporation: 'beta' (default, params.BUCKET) or 'fao56': in params.FAO56 bare-soil months ETa = Kr x ke_max x ET0
    with the FAO-56 two-stage Kr from the surface-layer depletion De (proposed option, 17 Oct).
    """
    model = evaporation or prm.BUCKET["evaporation_model"].value
    if model not in ("beta", "fao56"):
        raise ValueError(f"unknown evaporation model '{model}' (use 'beta' or 'fao56')")
    if "fc_mm" not in parcels.columns or "wp_mm" not in parcels.columns:
        parcels = add_hydraulics(parcels)
    w = _clean_weather(weather)
    b = prm.BUCKET
    beta_frac, sat_mm = b["beta_taw_fraction"].value, b["saturated_flag_rain_mm"].value
    k, ref = b["transient_k"].value, b["transient_ref_mm"].value

    fc = parcels["fc_mm"].to_numpy(dtype=float)
    wp = parcels["wp_mm"].to_numpy(dtype=float)
    taw = fc - wp
    ok = np.isfinite(fc) & np.isfinite(wp) & (taw > 0)
    P, ET0 = w["precip_mm"].to_numpy(dtype=float), w["et0_mm"].to_numpy(dtype=float)
    n, m = len(w), len(parcels)

    W = np.where(ok, fc, np.nan)
    water = np.empty((n, m))
    saturated = np.zeros((n, m), dtype=bool)
    fao = model == "fao56"
    if fao:
        tew, rew = fao56_tew_rew(parcels)
        bare = w["date"].dt.month.isin(prm.FAO56["bare_months"].value).to_numpy()
        ke_max = prm.FAO56["ke_max"].value
        De = np.zeros(m)
    with np.errstate(invalid="ignore", divide="ignore"):
        for t in range(n):
            if fao and bare[t]:
                kr = np.where(De <= rew, 1.0, np.clip((tew - De) / (tew - rew), 0.0, 1.0))
                et = ET0[t] * ke_max * kr
            else:
                et = ET0[t] * np.clip((W - wp) / (beta_frac * taw), 0.0, 1.0)
            W = W + P[t] - et
            saturated[t] = (W > fc) & (P[t] >= sat_mm)
            W = np.maximum(np.minimum(W, fc), wp)
            if fao:
                if bare[t]:
                    De = np.minimum(np.maximum(De - P[t], 0.0) + et, tew)
                    De = np.where(W >= fc - 1e-9, 0.0, De)
                else:
                    De = np.clip(fc - W, 0.0, tew)
            water[t] = W
        rwc = np.where(ok, (water - wp) / taw, np.nan)

    prev1 = np.concatenate([[0.0], P[:-1]])
    prev48 = P + prev1                       # last 48 h = today + yesterday
    rwc_eff = rwc + k * np.minimum(1.0, prev48 / ref)[:, None]

    def col(a):   # (days, parcels) -> parcel-major flat column
        return a.T.reshape(-1)

    def per_day(v):
        return np.tile(v, m)

    out = pd.DataFrame({
        "parcel_id": np.repeat(parcels["parcel_id"].to_numpy(), n),
        "date": np.tile(w["date"].to_numpy(), m),
        "W_mm": np.where(ok[None, :], water, np.nan).T.reshape(-1),
        "RWC": col(rwc), "RWC_eff": col(rwc_eff),
        "rain_today_mm": per_day(P), "rain_prev24h_mm": per_day(prev1), "rain_prev48h_mm": per_day(prev48),
        "tmax_c": per_day(w["tmax_c"].to_numpy(dtype=float)),
        "saturated_today": col(saturated), "origin": ORIGIN,
    })
    return out
