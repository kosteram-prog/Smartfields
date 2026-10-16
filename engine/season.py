"""Season simulation "FieldWindow" (owner: Marek). Spec 7.4-7.6.

Will the autumn sowing be finished by the deadline? Each historical autumn (AgERA5 2015-2024) is one
weather scenario. Day by day from the window start to the simulation end, the machine capacity is
allocated to the highest-priority open parcels whose day status allows work:
GO = full productivity, CAUTION = caution_weight (default 0.5), NO-GO = none.

  priority(parcels)                         -> parcels + priority score, rank, reason (7.6)
  simulate(status, parcels, own_ha_day, ...) -> (schedule, completion)   pure allocation core
  workable_days(status, parcels)            -> area share of GO per day
  season_from_inputs(parcels, status, params, ...) -> full result dict (no data loading)
  season(params, skip_dates, years, perfect_weather) -> contract function (loads data, statuses)

Day statuses come from Mirela's engine.status.status_table; until that module exists the stub is used
and the result says so in `status_source`. All parameters from engine/params.py.
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd

from engine import params as prm

ORIGIN = "modelled"
NA = "not available"
EPS = 1e-9
DEFAULT_MACHINE = "M2"     # demo drill (agreed defaults, decision B1); the UI passes the farmer's choice
MAX_CONTRACTOR_HA_DAY = 60


# --------------------------------------------------------------------------- parameters
def resolve_params(params: dict | None) -> dict:
    """Fill missing inputs with the agreed defaults from params.py."""
    p = dict(params or {})
    d = {
        "holding_id": prm.DEMO["holding_id"].value, "nuts3": prm.DEMO["nuts3"].value,
        "window_start": prm.SEASON["window_start"].value, "deadline": prm.SEASON["deadline"].value,
        "end": prm.SEASON["simulation_end"].value, "machine_id": DEFAULT_MACHINE,
        "units": prm.CAPACITY["own_units"].value, "hours": prm.CAPACITY["hours_per_day"].value,
        "ha_per_day": None, "contractor_ha_day": 0.0, "contractor_start": None,
        "caution_weight": prm.SEASON["caution_weight"].value, "passes": 1, "operation": "sowing",
        "load_class": None, "parcel_ids": None, "parcel_order": None,
    }
    d.update({k: v for k, v in p.items() if v is not None})
    m = prm.MACHINES[d["machine_id"]]
    if d["ha_per_day"] is None:
        d["ha_per_day"] = d["units"] * m["rate_ha_h"].value * d["hours"]
    if d["load_class"] is None:
        d["load_class"] = m["load_class"]
    if d["contractor_start"] is None:
        d["contractor_start"] = d["window_start"]
    return d


def autumn_crops() -> list[str]:
    return list(prm.PRIORITY["crop_sensitivity"].value)          # RAPE, BARL, COWT (spec 7.5)


# --------------------------------------------------------------------------- 7.6 priority
_CROP_NAMES = {"RAPE": "rapeseed", "BARL": "barley", "COWT": "wheat"}


def priority(parcels: pd.DataFrame) -> pd.DataFrame:
    """Score = w_crop x crop sensitivity + w_clay x clay class + w_area x (area >= 7 ha); rank 1 = first.

    Ties: crop sensitivity, then clay, then area (all descending), then parcel id.
    """
    pr = prm.PRIORITY
    out = parcels.copy()
    sens = out["crop"].map(pr["crop_sensitivity"].value).astype(float)
    clay = out["clay_pct"].astype(float)
    classes = pr["clay_class"].value                               # [(40, 3), (25, 2), (0, 1)]
    clay_cls = np.select([clay >= lo for lo, _ in classes], [float(s) for _, s in classes], default=np.nan)
    big = (out["area_ha"] >= pr["area_min_ha"].value).astype(float)
    out["priority"] = pr["w_crop"].value * sens + pr["w_clay"].value * clay_cls + pr["w_area"].value * big
    out["_sens"], out["_clay"] = sens, clay
    out = out.sort_values(["priority", "_sens", "_clay", "area_ha", "parcel_id"],
                          ascending=[False, False, False, False, True], na_position="last")
    out["rank"] = np.arange(1, len(out) + 1)
    out["reason"] = [
        ", ".join(filter(None, [
            f"{_CROP_NAMES.get(c, c)} ({'less tolerant of late sowing' if s >= 2 else 'tolerates later sowing'})"
            if s == s else None,
            f"heavy soil, clay {cl:.0f}% (sow while dry)" if cs == 3 else
            f"medium soil, clay {cl:.0f}%" if cs == 2 else f"light soil, clay {cl:.0f}%" if cs == cs else None,
            f"large parcel {a:.1f} ha" if b else None]))
        for c, s, cl, cs, a, b in zip(out["crop"], out["_sens"], out["_clay"],
                                      clay_cls[out.index.map(parcels.index.get_loc)], out["area_ha"], big[out.index])]
    return out.drop(columns=["_sens", "_clay"]).reset_index(drop=True)


# --------------------------------------------------------------------------- allocation core
def _md(year: int, mmdd: str) -> pd.Timestamp:
    return pd.Timestamp(f"{year}-{mmdd}")


def simulate(status: pd.DataFrame, parcels: pd.DataFrame, own_ha_day: float, *, caution_weight: float | None = None,
             contractor_ha_day: float = 0.0, contractor_start: str | None = None, skip_dates=(),
             perfect_weather: bool = False, window_start: str | None = None, end: str | None = None,
             years=None, order: list[str] | None = None):
    """Allocate capacity day by day. Returns (schedule, completion).

    status: parcel_id, date, status (GO / CAUTION / NO-GO); a missing parcel-day counts as not workable.
    schedule: one row per parcel and worked day (parcel_id, year, date, ha_done, ha_contractor, completion_date).
    completion: one row per year (year, completion_date = last parcel done, NaT if not done by `end`).
    """
    w = prm.SEASON["caution_weight"].value if caution_weight is None else caution_weight
    window_start = window_start or prm.SEASON["window_start"].value
    end = end or prm.SEASON["simulation_end"].value
    contractor_start = contractor_start or window_start
    if order is None:
        ids = priority(parcels).parcel_id.tolist()
    else:
        ids = list(order) + [p for p in priority(parcels).parcel_id if p not in set(order)]
    area0 = parcels.set_index("parcel_id").loc[ids, "area_ha"].to_numpy(dtype=float)
    prod_of = {"GO": 1.0, "CAUTION": float(w), "NO-GO": 0.0}
    prod = (status.pivot_table(index="date", columns="parcel_id", values="status", aggfunc="first")
            .reindex(columns=ids).apply(lambda col: col.map(prod_of)).fillna(0.0))
    if years is None:
        years = sorted(pd.to_datetime(status["date"]).dt.year.unique())
    skip = set(pd.to_datetime(list(skip_dates)))
    ones = np.ones(len(ids))

    rows, comp_rows, done_map = [], [], {}
    for y in years:
        rem = area0.copy()
        for d in pd.date_range(_md(y, window_start), _md(y, end)):
            if d in skip:
                continue
            cap_c = contractor_ha_day if contractor_ha_day > 0 and d >= _md(y, contractor_start) else 0.0
            total = own_ha_day + cap_c
            if total <= 0:
                continue
            prods = ones if perfect_weather else (prod.loc[d].to_numpy() if d in prod.index else ones * 0)
            budget = total
            for i, pid in enumerate(ids):
                if rem[i] <= EPS or prods[i] <= 0:
                    continue
                x = min(rem[i], budget * prods[i])
                budget -= x / prods[i]
                rem[i] -= x
                rows.append((pid, y, d, x, x * cap_c / total))
                if rem[i] <= EPS:
                    rem[i] = 0.0
                    done_map[(pid, y)] = d
                if budget <= EPS:
                    break
            if (rem <= EPS).all():
                break
        all_done = (rem <= EPS).all()
        comp_rows.append((y, max(done_map[(p, y)] for p in ids) if all_done and ids else pd.NaT,
                          int((rem <= EPS).sum()), float((area0 - rem).sum())))

    sched = pd.DataFrame(rows, columns=["parcel_id", "year", "date", "ha_done", "ha_contractor"])
    sched["completion_date"] = pd.to_datetime([done_map.get((p, y), pd.NaT) for p, y in zip(sched.parcel_id, sched.year)])
    sched["origin"] = ORIGIN
    comp = pd.DataFrame(comp_rows, columns=["year", "completion_date", "parcels_done", "ha_done"])
    comp["completion_date"] = pd.to_datetime(comp["completion_date"])
    comp["origin"] = ORIGIN
    return sched, comp


def p_by_deadline(completion: pd.DataFrame, deadline: str) -> float:
    """Share of years in which every parcel is done on or before the deadline (not done = late)."""
    if completion.empty:
        return float("nan")
    ok = [pd.notna(c) and c <= _md(y, deadline) for y, c in zip(completion.year, completion.completion_date)]
    return float(np.mean(ok))


def workable_days(status: pd.DataFrame, parcels: pd.DataFrame) -> pd.DataFrame:
    """Share of the parcel set with status GO, per day: by area (share_go) and by parcel count (share_go_parcels).

    The pre-event test's "3 workable days in 1-21 Oct 2016" counts parcels (11 of 21 GO on 14 Oct = 62 of 134 ha);
    by area 14 Oct is just below 50%. Which one the UI shows is a Product Leads choice.
    """
    s = status.merge(parcels[["parcel_id", "area_ha"]], on="parcel_id")
    s["go"] = s["status"] == "GO"
    s["go_ha"] = np.where(s["go"], s["area_ha"], 0.0)
    g = s.groupby("date").agg(go_ha=("go_ha", "sum"), ha=("area_ha", "sum"), go_n=("go", "mean")).reset_index()
    g["share_go"] = g["go_ha"] / g["ha"]
    g["share_go_parcels"] = g["go_n"]
    g["year"] = pd.to_datetime(g["date"]).dt.year
    g["origin"] = ORIGIN
    return g[["year", "date", "share_go", "share_go_parcels", "origin"]]


# --------------------------------------------------------------------------- full result (pure)
def _na_result(message: str) -> dict:
    return {"message": message, "P_by_deadline": {"value": NA, "unit": "share", "origin": ORIGIN},
            "P_by_deadline_with_contractor": None, "completion": pd.DataFrame(), "schedule": pd.DataFrame(),
            "parcel_order": [], "contractor_recommendation": {"message": NA, "origin": ORIGIN},
            "sensitivity": {"origin": ORIGIN}, "workable_days": pd.DataFrame()}


def season_from_inputs(parcels: pd.DataFrame, status: pd.DataFrame, params: dict | None,
                       skip_dates=None, years=None, perfect_weather: bool = False) -> dict:
    p = resolve_params(params)
    sel = parcels[parcels["crop"].isin(autumn_crops())]
    if p["parcel_ids"] is not None:
        sel = sel[sel["parcel_id"].isin(p["parcel_ids"])]
    if sel.empty:
        return _na_result("No autumn sowing on this farm: choose another operation.")
    status = status[status["parcel_id"].isin(sel["parcel_id"])]

    def run(contractor=0.0, weight=None, perfect=perfect_weather, skips=skip_dates):
        return simulate(status, sel, p["ha_per_day"], caution_weight=p["caution_weight"] if weight is None else weight,
                        contractor_ha_day=contractor, contractor_start=p["contractor_start"], skip_dates=skips or (),
                        perfect_weather=perfect, window_start=p["window_start"], end=p["end"], years=years,
                        order=p["parcel_order"])

    sched, comp = run(p["contractor_ha_day"])
    P = p_by_deadline(comp, p["deadline"])
    comp["on_time"] = [pd.notna(c) and c <= _md(y, p["deadline"]) for y, c in zip(comp.year, comp.completion_date)]

    # own capacity only (for the "with / without contractor" comparison)
    if p["contractor_ha_day"] > 0:
        _, comp_own = run(0.0)
        P_own = p_by_deadline(comp_own, p["deadline"])
    else:
        P_own = P

    # contractor recommendation: smallest step reaching the target P (spec 7.5)
    target, step = prm.CAPACITY["contractor_target_p"].value, prm.CAPACITY["contractor_step_ha_day"].value
    rec = {"extra_ha_day": NA, "p_with": NA, "ha_median": NA, "ha_max": NA, "start": p["contractor_start"],
           "target_p": target, "origin": ORIGIN}
    if P_own >= target:
        rec.update(extra_ha_day=0, p_with=P_own, ha_median=0.0, ha_max=0.0,
                   message="No contractor needed: own capacity already reaches the target.")
    else:
        for extra in range(step, MAX_CONTRACTOR_HA_DAY + 1, step):
            s_c, c_c = run(float(extra))
            p_c = p_by_deadline(c_c, p["deadline"])
            if p_c >= target:
                ha = s_c.groupby("year").ha_contractor.sum().reindex(c_c.year, fill_value=0.0)
                cs = pd.Timestamp("2000-" + p["contractor_start"])
                rec.update(extra_ha_day=extra, p_with=p_c, ha_median=float(ha.median()), ha_max=float(ha.max()),
                           message=f"Book a contractor for ~{ha.median():.0f} ha (+{extra} ha/day) "
                                   f"from {cs.day} {cs:%b}.")
                break
        else:
            rec["message"] = f"Even +{MAX_CONTRACTOR_HA_DAY} ha/day does not reach {target:.0%}."

    sens = {"origin": ORIGIN}
    for wgt in prm.SEASON["caution_weight_options"].value:
        sens[wgt] = p_by_deadline(run(p["contractor_ha_day"], weight=wgt)[1], p["deadline"])

    # parcel order table with median completion and share of late years
    pr = priority(sel)
    late, med = [], []
    for pid in pr.parcel_id:
        cds = sched[sched.parcel_id == pid].groupby("year").completion_date.first().reindex(comp.year)
        late.append(float(np.mean([pd.isna(c) or c > _md(y, p["deadline"]) for y, c in zip(comp.year, cds)])))
        days = [(c - _md(y, p["window_start"])).days for y, c in zip(comp.year, cds) if pd.notna(c)]
        med.append((pd.Timestamp("2000-" + p["window_start"]) + pd.Timedelta(days=float(np.median(days)))).strftime("%d %b")
                   if len(days) == len(comp) else NA)
    order_rows = [{"rank": int(r.rank), "parcel_id": r.parcel_id, "crop": r.crop, "area_ha": float(r.area_ha),
                   "clay_pct": float(r.clay_pct), "priority": float(r.priority), "reason": r.reason,
                   "median_done": m, "share_years_late": l, "origin": "assumption+modelled"}
                  for r, m, l in zip(pr.itertuples(), med, late)]

    return {
        "P_by_deadline": {"value": P_own, "unit": "share", "origin": ORIGIN, "n_years": int(len(comp))},
        "P_by_deadline_with_contractor": ({"value": P, "unit": "share", "origin": ORIGIN, "extra_ha_day": p["contractor_ha_day"]}
                                          if p["contractor_ha_day"] > 0 else None),
        "completion": comp, "schedule": sched, "parcel_order": order_rows,
        "contractor_recommendation": rec, "sensitivity": sens,
        "workable_days": workable_days(status, sel), "inputs": p, "message": None,
    }


# --------------------------------------------------------------------------- data + statuses (cached)
def _status_provider():
    try:
        from engine import status as st_mod                          # Mirela's module, when it exists
        if hasattr(st_mod, "status_table"):
            return st_mod.status_table, "engine.status"
    except ImportError:
        pass
    from engine import stubs
    return stubs.status_table, "stub (engine/stubs.py)"


@lru_cache(maxsize=16)
def _inputs(data_dir: str, holding_id: str, nuts3: str, load_class: str, passes: int, operation: str,
            window_start: str, end: str):
    from engine import data, soil
    farm = data.load_farm(holding_id)
    autumn = farm[farm["crop"].isin(autumn_crops())]
    if autumn.empty:
        return farm, pd.DataFrame(columns=["parcel_id", "date", "status"]), "none"
    sw = soil.soil_water(autumn, data.load_weather(nuts3))
    md = sw["date"].dt.strftime("%m-%d")
    sw = sw[(md >= window_start) & (md <= end)]
    status_table, source = _status_provider()
    st = status_table(sw, autumn, load_class, passes, operation)
    return farm, st[["parcel_id", "date", "status"]].reset_index(drop=True), source


def season(params: dict | None = None, skip_dates=None, years=None, perfect_weather: bool = False) -> dict:
    """Contract function: Season simulation for the farm in params (defaults: FARM-13525, PL415, M2, 1-15 Oct)."""
    import config
    p = resolve_params(params)
    farm, status, source = _inputs(str(config.get_data_dir()), p["holding_id"], p["nuts3"], p["load_class"],
                                   int(p["passes"]), p["operation"], p["window_start"], p["end"])
    res = season_from_inputs(farm, status.copy(), p, skip_dates=skip_dates, years=years, perfect_weather=perfect_weather)
    res["status_source"] = source
    return res
