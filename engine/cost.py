"""Cost of delay, contractor value and "if you wait" (spec 6.8, 7.5 cost part, 7.15; decisions D9-D14).

Written by Marek's agent for Mirela's slice (agreed 16 Oct 20:22); Mirela reviews.

For each year and parcel:
  days_late = max(0, completion_date - optimum_end(crop) - grace)
  loss_pct  = min(cap, rate x days_late)              rate low / default / high (% per day)
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
    """
    import config
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
    rates = {r: cst["loss_rate_pct_per_day"][r].value for r in RATES} | (p.get("rates") or {})
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
            for rate, v in rates.items():
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


def entry_cost(status: str, load_class: str, crop: str, area_ha: float, params: dict | None = None) -> dict:
    """Spec 6.8.3 (Add-on 3): year-1 yield loss on the trafficked area when the farmer goes although status != GO.

    eur = loss % (status, load class) x trafficked share x area x expected yield x price. Illustrative: needs
    calibration; part of the damage (subsoil) can last for years.
    """
    p = params or {}
    out = {"status": status, "load_class": load_class, "unit": "EUR", "label": "illustrative, needs calibration",
           "origin": "synthetic+assumption",
           "note": "Year 1 only; part of the damage can last for years (subsoil compaction)."}
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
