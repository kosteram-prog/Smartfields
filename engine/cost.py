"""Cost of delay, contractor value and "if you wait" (spec 6.8, 7.5 cost part, 7.15; decisions D9-D14).

Written by Marek's agent for Mirela's slice (agreed 16 Oct 20:22); Mirela reviews.

For each year and parcel:
  days_late = max(0, completion_date - optimum_end(crop) - grace)
  loss_pct  = min(cap, rate x days_late)              rate low / default / high (% per day), per crop
                                                      (barley 0.43, wheat 1.0 %/day; decision 17 Oct)
  cost_eur  = loss_pct / 100 x expected_yield x area_ha x price
Late-start part = the same with the perfect-weather schedule (all days GO from the window start);
weather part = total - late start (the headline, D14). Missing yield, price or optimum_end -> "not available".

  default_economics(holding_id)                -> expected yield and price per crop (synthetic, editable)
  season_cost(schedule, parcels, params)       -> per_year, median, worst_year, origin
  contractor_value(cost_without, cost_with, contractor_ha, contractor_price) -> value and net benefit
  wait_cost(date, params)                      -> EUR if you wait one day (replay year only), days to first GO
  season_costs(params)                         -> convenience for the UI: season + costs + contractor value
  entry_cost(status, load_class, crop, area_ha, params) -> "If you go now": illustrative year-1 loss from wet traffic
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from engine import params as prm

NA = "not available"
ORIGIN = "real+synthetic+assumption"
RATES = ("low", "default", "high")
PARTS = ("total", "late_start", "weather")


def _num(x) -> bool:
    return isinstance(x, (int, float, np.integer, np.floating)) and not pd.isna(x)


# --------------------------------------------------------------------------- inputs
def default_economics(holding_id: str | None = None) -> dict:
    """Expected yield = mean synthetic yield of the farm's parcels per crop; price = mean Jul-Aug market price.

    Years: the replay range (2015-2024) clipped to the synthetic campaigns (2017-2026) -> 2017-2024.
    Without extracts, uses the stub yield/price table so the UI can still recalculate.
    """
    import config
    if config.data_dir_or_none() is None:
        from engine import stubs
        return stubs.economics()
    from engine import data
    holding_id = holding_id or prm.DEMO["holding_id"].value
    y0, y1 = prm.DEMO["replay_year_min"].value, prm.DEMO["replay_year_max"].value
    hv = data.load_operations("harvest", holding_id)
    hv = hv[hv["year"].between(y0, y1)]
    yields = hv.groupby("crop")["yield_t_ha"].mean().round(3).to_dict()
    prices = pd.read_parquet(config.get_data_dir() / "prices.parquet")
    p = prices[prices["month"].isin(prm.COST["price_months"].value) & prices["year"].between(y0, y1)]
    price = p.groupby("product")["price_eur_t"].mean().round(1).to_dict()
    return {"yield_t_ha": yields, "price_eur_t": price, "origin": "synthetic",
            "note": "Synthetic yields do not react to weather: enter your own expected yield for a real decision."}


def _completion(schedule: pd.DataFrame, parcel_ids, years) -> pd.DataFrame:
    """Completion date per parcel and year; a parcel not finished gets NaT."""
    if schedule is None or len(schedule) == 0:
        idx = pd.MultiIndex.from_product([list(parcel_ids), list(years)], names=["parcel_id", "year"])
        return pd.DataFrame({"completion_date": pd.NaT}, index=idx).reset_index()
    c = schedule.groupby(["parcel_id", "year"])["completion_date"].first()
    idx = pd.MultiIndex.from_product([list(parcel_ids), list(years)], names=["parcel_id", "year"])
    return c.reindex(idx).rename("completion_date").reset_index()


def _cost_table(schedule, parcels, years, params) -> pd.DataFrame:
    """Cost per parcel-year for each rate (EUR), or NA where an input is missing."""
    cst = prm.COST
    p = params or {}
    yields, prices = p.get("yield_t_ha") or {}, p.get("price_eur_t") or {}
    optimum = {k: v.value for k, v in cst["optimum_end"].items()} | (p.get("optimum_end") or {})
    grace = p.get("grace_days", cst["grace_days"].value)
    cap = p.get("cap_pct", cst["loss_cap_pct"].value)
    fallback = {r: cst["loss_rate_pct_per_day"][r].value for r in RATES}
    by_crop = {k: v.value for k, v in cst.get("loss_rate_by_crop", {}).items()}

    def rates_for(crop):   # explicit params["rates"] apply to every crop; else the crop's own rate; else the fallback
        if p.get("rates"):
            return fallback | p["rates"]
        return by_crop.get(crop, fallback)
    end = p.get("end", prm.SEASON["simulation_end"].value)

    comp = _completion(schedule, parcels["parcel_id"], years).merge(
        parcels[["parcel_id", "crop", "area_ha"]], on="parcel_id", how="left")
    rows = []
    for r in comp.itertuples():
        opt, yld, prc = optimum.get(r.crop), yields.get(r.crop), prices.get(r.crop)
        done = r.completion_date if pd.notna(r.completion_date) else pd.Timestamp(f"{r.year}-{end}")
        row = {"parcel_id": r.parcel_id, "year": r.year, "crop": r.crop, "area_ha": r.area_ha,
               "completion_date": r.completion_date, "not_done": pd.isna(r.completion_date)}
        if opt is None or not _num(yld) or not _num(prc):
            row["days_late"] = NA
            for rate in RATES:
                row[rate] = NA
        else:
            days_late = max(0, (done - pd.Timestamp(f"{r.year}-{opt}")).days - grace)
            row["days_late"] = days_late
            for rate, v in rates_for(r.crop).items():
                row[rate] = min(cap, v * days_late) / 100.0 * yld * r.area_ha * prc
        rows.append(row)
    return pd.DataFrame(rows)


def _sum(s: pd.Series):
    return NA if any(not _num(v) for v in s) else float(s.sum())


# --------------------------------------------------------------------------- contract functions
def season_cost(schedule: pd.DataFrame, parcels: pd.DataFrame, params: dict | None = None) -> dict:
    """Farm cost of delay per year at the low / default / high loss rate.

    params: yield_t_ha {crop}, price_eur_t {crop}; optional optimum_end {crop: 'MM-DD'}, grace_days, cap_pct,
    rates {low/default/high}, years, perfect_schedule (season(perfect_weather=True)['schedule'] for the split).
    """
    p = params or {}
    sel = parcels[parcels["crop"].isin(list(prm.COST["optimum_end"]))]
    years = p.get("years") or (sorted(schedule["year"].unique()) if schedule is not None and len(schedule) else [])
    tot = _cost_table(schedule, sel, years, p)
    perfect = p.get("perfect_schedule")
    late = _cost_table(perfect, sel, years, p) if perfect is not None else None

    rows = []
    for y in years:
        t = tot[tot["year"] == y]
        row = {"year": int(y), "parcels_not_done": int(t["not_done"].sum())}
        for rate in RATES:
            row[f"total_{rate}"] = _sum(t[rate])
            if late is not None:
                ls = _sum(late[late["year"] == y][rate])
                row[f"late_start_{rate}"] = ls
                row[f"weather_{rate}"] = (row[f"total_{rate}"] - ls) if _num(ls) and _num(row[f"total_{rate}"]) else NA
            else:
                row[f"late_start_{rate}"] = row[f"weather_{rate}"] = NA
        rows.append(row)
    per_year = pd.DataFrame(rows)
    median, worst = {}, {"year": NA}
    for part in PARTS:
        for rate in RATES:
            col = f"{part}_{rate}"
            vals = per_year[col] if col in per_year else pd.Series(dtype=object)
            median[col] = float(np.median(vals)) if len(vals) and all(_num(v) for v in vals) else NA
    key = "weather_default" if late is not None else "total_default"
    if len(per_year) and all(_num(v) for v in per_year[key]):
        w = per_year.loc[per_year[key].astype(float).idxmax()]
        worst = {"year": int(w["year"])} | {f"{part}_{rate}": w[f"{part}_{rate}"] for part in PARTS for rate in RATES}
    out = {"per_year": per_year.assign(origin=ORIGIN), "median": median, "worst_year": worst,
           "by_parcel": tot, "unit": "EUR", "headline": key, "origin": ORIGIN}
    if schedule is not None and "ha_contractor" in schedule:
        out["contractor_ha_by_year"] = schedule.groupby("year")["ha_contractor"].sum().reindex(years, fill_value=0.0)
    return out


def contractor_value(cost_without: dict, cost_with: dict, contractor_ha=None, contractor_price=None) -> dict:
    """Contractor value = cost without - cost with (default rate), per year; net = value - price x hectares."""
    a = cost_without["per_year"].set_index("year")["total_default"]
    b = cost_with["per_year"].set_index("year")["total_default"]
    if not all(_num(v) for v in list(a) + list(b)):
        return {"value_median": NA, "value_worst": NA, "net_benefit_median": NA, "net_benefit_worst": NA,
                "worst_year": NA, "unit": "EUR", "origin": ORIGIN}
    value = (a - b).astype(float)
    worst_year = int(value.idxmax())
    out = {"value_by_year": value, "value_median": float(value.median()), "value_worst": float(value.max()),
           "worst_year": worst_year, "unit": "EUR", "origin": ORIGIN}
    if contractor_price is None or not _num(contractor_price):
        out.update(net_benefit_median=NA, net_benefit_worst=NA,
                   message="Enter the contractor price to compare.")
        return out
    if contractor_ha is None:
        ha = cost_with.get("contractor_ha_by_year")
        if ha is None:
            out.update(net_benefit_median=NA, net_benefit_worst=NA)
            return out
        ha = ha.reindex(value.index, fill_value=0.0)
    else:
        ha = pd.Series(float(contractor_ha), index=value.index)
    fee = ha * float(contractor_price)
    net = value - fee
    out.update(contractor_ha_median=float(ha.median()), contractor_fee_median=float(fee.median()),
               contractor_fee_worst=float(fee[worst_year]), net_benefit_by_year=net,
               net_benefit_median=float(net.median()), net_benefit_worst=float(net[worst_year]))
    return out


def _econ_params(params: dict | None) -> dict:
    p = dict(params or {})
    if not p.get("yield_t_ha") or not p.get("price_eur_t"):
        econ = default_economics(p.get("holding_id"))
        p.setdefault("yield_t_ha", econ["yield_t_ha"])
        p.setdefault("price_eur_t", econ["price_eur_t"])
        p["yield_t_ha"] = p["yield_t_ha"] or econ["yield_t_ha"]
        p["price_eur_t"] = p["price_eur_t"] or econ["price_eur_t"]
    return p


def wait_cost(date, params: dict | None = None) -> dict:
    """EUR lost by not sowing on `date` (replay year only): season_cost(skip date) - season_cost(use date).

    Optional params: parcel_id, machine_id, load_pct, passes -> days_to_first_go from engine.today.
    """
    from engine import data, season
    d = pd.Timestamp(date)
    p = season.resolve_params(params)
    md = d.strftime("%m-%d")
    out = {"date": d, "unit": "EUR", "origin": ORIGIN, "days_to_first_go": NA}
    if not (p["window_start"] <= md <= p["end"]):
        return out | {"eur": NA, "eur_low": NA, "eur_high": NA,
                      "message": f"{d:%d %b} is outside the sowing window ({p['window_start']} to {p['end']})."}
    ep = _econ_params(params)
    farm = data.load_farm(p["holding_id"])
    base = season.season(params, years=[d.year])
    skip = season.season(params, years=[d.year], skip_dates=[d])
    c0, c1 = season_cost(base["schedule"], farm, ep | {"years": [d.year]}), \
        season_cost(skip["schedule"], farm, ep | {"years": [d.year]})
    res = {}
    for rate in RATES:
        a, b = c0["per_year"][f"total_{rate}"].iloc[0], c1["per_year"][f"total_{rate}"].iloc[0]
        res[rate] = round(b - a, 0) if _num(a) and _num(b) else NA
    out |= {"eur": res["default"], "eur_low": res["low"], "eur_high": res["high"]}
    if res["default"] == 0:
        out["message"] = "EUR 0: waiting one day does not change the finish (nothing workable, or still in time)."
    if params and params.get("parcel_id"):
        from engine.today import today
        t = today(params["parcel_id"], d, params.get("machine_id", p["machine_id"]), params.get("load_pct", 100),
                  params.get("passes", 1), "sowing")
        out["days_to_first_go"] = t.get("days_to_first_go", NA)
    return out


def season_costs(params: dict | None = None) -> dict:
    """Everything the Season cost cards need: cost without / with contractor and the contractor value."""
    from engine import data, season
    p = season.resolve_params(params)
    ep = _econ_params(params)
    farm = data.load_farm(p["holding_id"])
    own_p = dict(params or {}) | {"contractor_ha_day": 0.0}
    own = season.season(own_p)
    perfect = season.season(own_p, perfect_weather=True)
    cost_own = season_cost(own["schedule"], farm, ep | {"perfect_schedule": perfect["schedule"]})
    out = {"cost": cost_own, "economics": {"yield_t_ha": ep["yield_t_ha"], "price_eur_t": ep["price_eur_t"],
                                          "origin": "synthetic"}}
    extra = float((params or {}).get("contractor_ha_day") or 0.0)
    if extra > 0:
        withc = season.season(dict(params or {}))
        cost_with = season_cost(withc["schedule"], farm, ep)
        out["cost_with_contractor"] = cost_with
        out["contractor_value"] = contractor_value(cost_own, cost_with, None,
                                                   (params or {}).get("contractor_price",
                                                                      prm.COST["contractor_price_eur_ha"].value))
        out["contractor_ha_day"] = extra
    return out


def _persistent(out: dict, factor: float) -> dict:
    """Long-term subsoil part (RECARE 2018): pct_per_year x factor on the trafficked area, for `years` (undiscounted)."""
    pers = prm.WET_TRAFFIC_LOSS["persistent"]
    rate, years = pers["pct_per_year"].value, pers["years"].value
    base = {"persistent_years": years, "persistent_pct_per_year": rate * factor,
            "persistent_note": f"Subsoil: about {rate:g}% of yield per year on the trafficked area for ~{years} years "
                               "(RECARE 2018: 6-12% after heavy wet traffic), undiscounted, illustrative"}
    if factor == 0:
        return out | base | {"persistent_eur_per_year": 0.0, "persistent_eur_total": 0.0}
    yld, prc, area, share = out.get("yield_t_ha"), out.get("price_eur_t"), out.get("area_ha"), out.get("trafficked_share")
    if not all(_num(v) for v in (yld, prc, area, share)):
        return out | base | {"persistent_eur_per_year": NA, "persistent_eur_total": NA}
    per_year = rate * factor / 100.0 * share * area * yld * prc
    return out | base | {"persistent_eur_per_year": round(per_year, 0), "persistent_eur_total": round(per_year * years, 0)}


def _table_factor(status: str, load_class: str) -> float:
    pers = prm.WET_TRAFFIC_LOSS["persistent"]
    return pers["status_factor"].value.get(status, 0.0) * pers["class_factor"].value.get(load_class, 0.0)


def entry_cost(status: str, load_class: str, crop: str, area_ha: float, params: dict | None = None,
               persistent_factor: float | None = None) -> dict:
    """Spec 6.8.3 (Add-on 3): year-1 yield loss on the trafficked area when the farmer goes although status != GO,
    plus (decision 17 Oct) the long-term subsoil part, shown separately (RECARE 2018).

    eur = loss % (status, load class) x trafficked share x area x expected yield x price. Illustrative: needs
    calibration. persistent_factor: None -> from the table (L4/L5 on CAUTION / NO-GO); the tyre check passes its own.
    """
    factor = _table_factor(status, load_class) if persistent_factor is None else persistent_factor
    return _persistent(_entry_year1(status, load_class, crop, area_ha, params) | {"area_ha": area_ha}, factor)


def _entry_year1(status: str, load_class: str, crop: str, area_ha: float, params: dict | None = None) -> dict:
    p = params or {}
    out = {"status": status, "load_class": load_class, "unit": "EUR", "label": "illustrative, needs calibration",
           "origin": "synthetic+assumption",
           "note": "Year 1; the long-term subsoil part is shown separately."}
    if status == "GO":
        return out | {"eur": 0.0, "loss_pct": 0.0, "message": "EUR 0 expected: soil can carry this load today."}
    if status not in prm.WET_TRAFFIC_LOSS or load_class not in prm.WET_TRAFFIC_LOSS[status]:
        return out | {"eur": NA, "loss_pct": NA}
    pct = prm.WET_TRAFFIC_LOSS[status][load_class].value
    share = p.get("trafficked_share", prm.WET_TRAFFIC_LOSS["trafficked_share"].value)
    yld = (p.get("yield_t_ha") or {}).get(crop)
    prc = (p.get("price_eur_t") or {}).get(crop)
    if yld is None or prc is None:
        try:
            econ = default_economics(p.get("holding_id"))
            yld = econ["yield_t_ha"].get(crop) if yld is None else yld
            prc = econ["price_eur_t"].get(crop) if prc is None else prc
        except Exception:
            pass
    if not (_num(yld) and _num(prc) and _num(area_ha)):
        return out | {"eur": NA, "loss_pct": pct, "trafficked_share": share}
    eur = pct / 100.0 * share * float(area_ha) * float(yld) * float(prc)
    return out | {"eur": round(eur, 0), "loss_pct": pct, "trafficked_share": share,
                  "trafficked_ha": round(share * float(area_ha), 2), "yield_t_ha": yld, "price_eur_t": prc}


def entry_cost_tyre(check: dict, load_class: str, crop: str, area_ha: float, params: dict | None = None) -> dict:
    """'If you go now' with the farmer's tyre pressure (17 Oct, proposed): the tyre-based compaction class picks the
    row of the 6.8.3 table (green -> EUR 0, yellow -> CAUTION row, red -> NO-GO row); the load class stays the column.
    """
    if not check or not check.get("assessed"):
        return {"eur": NA, "loss_pct": NA, "method": "tyre", "unit": "EUR", "origin": "synthetic+assumption",
                "label": "illustrative, needs calibration",
                "message": (check or {}).get("reason", "Tyre check not available.")}
    factor = prm.WET_TRAFFIC_LOSS["persistent"]["tyre_subsoil_factor"].value.get(check.get("subsoil"), 0.0)
    out = entry_cost(check["cost_row"], load_class, crop, area_ha, params, persistent_factor=factor)
    return out | {"method": "tyre", "compaction_class": check["overall"]}


# --------------------------------------------------------------------------- avoidable losses (17 Oct)
def avoidable_from_ops(ops: pd.DataFrame, farm: pd.DataFrame, econ: dict) -> pd.DataFrame:
    """Per year: year-1 and long-term subsoil loss of recorded operations done on CAUTION / NO-GO days.

    ops: date, parcel_id, status, load_class (engine.lint.wet_day_operations rows). Compaction does not add up over
    passes, so each parcel-year counts its worst operation only.
    """
    cols = ["year", "year1_eur", "subsoil_eur_per_year", "n_operations"]
    bad = ops[ops["status"].isin(["CAUTION", "NO-GO"])]
    if bad.empty:
        return pd.DataFrame(columns=cols)
    f = farm.set_index("parcel_id")
    rows = []
    for r in bad.itertuples():
        if r.parcel_id not in f.index:
            continue
        e = entry_cost(r.status, r.load_class, f.at[r.parcel_id, "crop"], f.at[r.parcel_id, "area_ha"], econ)
        rows.append({"year": pd.Timestamp(r.date).year, "parcel_id": r.parcel_id,
                     "y1": e["eur"] if _num(e["eur"]) else np.nan,
                     "per": e.get("persistent_eur_per_year") if _num(e.get("persistent_eur_per_year")) else np.nan})
    t = pd.DataFrame(rows)
    pw = t.groupby(["year", "parcel_id"]).agg(y1=("y1", "max"), per=("per", "max"))
    out = pw.groupby("year").agg(year1_eur=("y1", "sum"), subsoil_eur_per_year=("per", "sum"))
    out["n_operations"] = t.groupby("year").size()
    return out.reset_index()[cols]


def avoidable_losses(holding_id: str | None = None) -> dict:
    """What FieldGo could have avoided on this farm: compaction from recorded operations on CAUTION / NO-GO days
    (year 1 + long-term subsoil part), and the weather part of the sowing-delay cost (median year).

    Upper bound: the synthetic operation dates are random with respect to weather, real farmers already avoid the
    worst days, and not every operation can be moved (FieldGo also offers lighter machines, loads, tyre pressure).
    """
    from engine import data, lint
    holding_id = holding_id or prm.DEMO["holding_id"].value
    farm = data.load_farm(holding_id)
    econ = default_economics(holding_id)
    w = lint.wet_day_operations(holding_id, None)
    per_year = avoidable_from_ops(w["rows"], farm, econ)
    full = per_year["n_operations"] >= 0.5 * per_year["n_operations"].median() if len(per_year) else []
    years = per_year[full]                                      # skip partial years (e.g. autumn before the first campaign)
    delay = season_costs({"holding_id": holding_id})["cost"]["median"].get("weather_default", NA)
    pers = prm.WET_TRAFFIC_LOSS["persistent"]
    return {"per_year": per_year,
            "year1_eur_mean": float(years["year1_eur"].mean()) if len(years) else NA,
            "subsoil_eur_per_year_mean": float(years["subsoil_eur_per_year"].mean()) if len(years) else NA,
            "subsoil_years": pers["years"].value,
            "delay_weather_eur_median": delay, "area_ha": float(farm["area_ha"].sum()),
            "years": [int(y) for y in years["year"]], "unit": "EUR", "origin": "synthetic+real+assumption",
            "label": "upper bound, illustrative",
            "note": "Synthetic operation dates are random with respect to weather; real farmers already avoid some "
                    "of the worst days, so the realistic share is lower (e.g. half)."}


# --------------------------------------------------------------------------- continuous "if you go now" (17 Oct evening)
def _overstress(check: dict, layer: str) -> float:
    p = check["profile"]
    p = p[p.layer == layer]
    return float(np.mean(np.clip(1.0 - p.strength_kpa / p.stress_kpa, 0.0, None)))


def _subsoil_anchor() -> float:
    from engine import compaction
    a = prm.GO_NOW_MODEL["subsoil_anchor"].value
    return _overstress(compaction.check(a["wheel_t"], a["bar"], a["clay"], a["sand"], a["om"], a["rwc"]), "subsoil")


def go_now_cost(status: str, rwc_eff, axle_t, load_class: str, clay_pct, sand_pct, om_pct, crop: str, area_ha,
                inflation_bar=None, passes: int = 1, params: dict | None = None) -> dict:
    """'If you go now' that reacts to the machine, the tyres and how wet the soil is.

    year-1 % = anchor (15 %) x min(cap, axle / 11 t) x (bar / 2.0)^0.5 x wetness
      wetness = 0 on GO; otherwise (RWC - GO limit of the class) / (1.10 - GO limit), at least 0.25 (CAUTION) /
      0.5 (NO-GO) so a NO-GO from rain still counts
    subsoil %/yr = RECARE 6 % x min(cap, subsoil overstress / anchor overstress) from the compaction check
      (Söhne stress vs precompression stress at 30-80 cm, same wetness), only when the status is not GO
    EUR = % x trafficked share x area x expected yield x price. Illustrative, needs calibration.
    """
    from engine import compaction
    from engine.status import _thresholds
    m, p = prm.GO_NOW_MODEL, params or {}
    bar = float(inflation_bar) if _num(inflation_bar) else m["default_tyre_bar"].value.get(load_class, 1.4)
    out = {"status": status, "load_class": load_class, "axle_t": axle_t, "inflation_bar": bar, "unit": "EUR",
           "method": "continuous", "label": "illustrative, needs calibration", "origin": "modelled+synthetic+assumption",
           "persistent_years": prm.WET_TRAFFIC_LOSS["persistent"]["years"].value}
    if not all(_num(v) for v in (rwc_eff, axle_t, clay_pct, sand_pct)):
        return out | {"eur": NA, "loss_pct": NA, "persistent_eur_per_year": NA, "persistent_eur_total": NA}
    go_thr, _ = _thresholds(load_class, float(clay_pct), float(sand_pct), passes)
    go_thr = float(go_thr)
    if status == "GO":
        wet = 0.0
    else:
        span = max(1e-6, m["wet_full_rwc"].value - go_thr)
        wet = float(np.clip((float(rwc_eff) - go_thr) / span, 0.0, 1.0))
        wet = max(wet, m["status_floor"].value.get(status, 0.0))
    axle_f = min(m["axle_factor_max"].value, (float(axle_t) / m["anchor_axle_t"].value) ** m["axle_exponent"].value)
    tyre_f = (bar / m["anchor_bar"].value) ** m["tyre_exponent"].value
    pct1 = m["anchor_pct"].value * axle_f * tyre_f * wet
    sub_f, sub_class = 0.0, None
    if status != "GO":
        chk = compaction.check(float(axle_t) / 2.0, bar, clay_pct, sand_pct, om_pct if _num(om_pct) else 2.0,
                               float(rwc_eff))
        if chk.get("assessed", True) and "profile" in chk:
            sub_f = min(m["subsoil_factor_max"].value, _overstress(chk, "subsoil") / max(1e-6, _subsoil_anchor()))
            sub_class = chk.get("subsoil")
    pers_rate = prm.WET_TRAFFIC_LOSS["persistent"]["pct_per_year"].value
    pct_sub = pers_rate * sub_f
    share = p.get("trafficked_share", prm.WET_TRAFFIC_LOSS["trafficked_share"].value)
    yld = (p.get("yield_t_ha") or {}).get(crop)
    prc = (p.get("price_eur_t") or {}).get(crop)
    if yld is None or prc is None:
        try:
            econ = default_economics(p.get("holding_id"))
            yld = econ["yield_t_ha"].get(crop) if yld is None else yld
            prc = econ["price_eur_t"].get(crop) if prc is None else prc
        except Exception:
            pass
    out |= {"loss_pct": round(pct1, 2), "persistent_pct_per_year": round(pct_sub, 2), "trafficked_share": share,
            "drivers": {"wetness": round(wet, 2), "axle": round(axle_f, 2), "tyre": round(tyre_f, 2),
                        "subsoil": round(sub_f, 2), "go_limit_rwc": round(go_thr, 3)},
            "subsoil_class": sub_class}
    if not (_num(yld) and _num(prc) and _num(area_ha)):
        return out | {"eur": NA, "persistent_eur_per_year": NA, "persistent_eur_total": NA}
    base = share * float(area_ha) * float(yld) * float(prc) / 100.0
    per_year = pct_sub * base
    return out | {"eur": round(pct1 * base, 0), "persistent_eur_per_year": round(per_year, 0),
                  "persistent_eur_total": round(per_year * out["persistent_years"], 0),
                  "trafficked_ha": round(share * float(area_ha), 2), "yield_t_ha": yld, "price_eur_t": prc,
                  "eur_per_pct": round(base, 1)}


def go_or_wait(go: dict, wait: dict) -> dict:
    """Compare 'go now' (year 1 + subsoil years, undiscounted) with 'wait one day' and say which costs less."""
    g1, gp = go.get("eur"), go.get("persistent_eur_total")
    w = wait.get("eur")
    if not (_num(g1) and _num(w)):
        return {"verdict": NA, "go_total": NA, "wait": w}
    gt = float(g1) + (float(gp) if _num(gp) else 0.0)
    if gt == 0:
        v = "go"
    elif gt < 0.8 * w:
        v = "go"
    elif gt > 1.25 * w:
        v = "wait"
    else:
        v = "close"
    return {"verdict": v, "go_total": round(gt, 0), "go_year1": g1, "wait": w,
            "difference": round(gt - float(w), 0)}


def day_plan_cost(plots: pd.DataFrame, capacity_ha: float, wait_eur=None) -> dict:
    """Today's work for one machine: GO plots first (EUR 0); if they do not fill the day, the cheapest wet plots
    (EUR per ha, year 1 + subsoil years) until the capacity is used. Compared with leaving that area for later.

    plots: status, area_ha, year1_eur, subsoil_eur_total (per plot). wait_eur: cost of skipping the whole day.
    """
    go_ha = float(plots.loc[plots.status == "GO", "area_ha"].sum())
    out = {"capacity_ha": float(capacity_ha), "go_ha": round(go_ha, 1), "wet_plan": [], "wet_ha": 0.0,
           "wet_eur": 0.0, "wait_part_eur": NA}
    if go_ha >= capacity_ha:
        return out | {"verdict": "go_plots_only", "message": f"GO plots ({go_ha:.0f} ha) fill today's capacity "
                      f"(~{capacity_ha:.0f} ha): no reason to drive on wet soil."}
    need = capacity_ha - go_ha
    wet = plots[plots.status.isin(["CAUTION", "NO-GO"])].copy()
    wet["total"] = pd.to_numeric(wet.year1_eur, errors="coerce").fillna(0) + \
        pd.to_numeric(wet.subsoil_eur_total, errors="coerce").fillna(0)
    wet = wet[wet.area_ha > 0].assign(per_ha=lambda d: d.total / d.area_ha).sort_values("per_ha")
    plan, eur, ha = [], 0.0, 0.0
    for r in wet.itertuples():
        if ha >= need:
            break
        take = min(float(r.area_ha), need - ha)
        plan.append({"parcel_id": r.parcel_id, "ha": round(take, 1), "eur": round(r.per_ha * take, 0)})
        eur += r.per_ha * take
        ha += take
    out |= {"wet_plan": plan, "wet_ha": round(ha, 1), "wet_eur": round(eur, 0)}
    if not _num(wait_eur):
        return out | {"verdict": NA}
    part = float(wait_eur) * ha / capacity_ha if capacity_ha > 0 else NA
    v = go_or_wait({"eur": eur, "persistent_eur_total": 0.0}, {"eur": part})["verdict"]
    return out | {"wait_part_eur": round(part, 0), "verdict": {"go": "fill_with_wet", "wait": "go_plots_only_wait",
                                                               "close": "close"}.get(v, v)}
