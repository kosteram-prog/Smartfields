"""Find a safer plan (spec 7.8): three levers only, in this order, never worse than the input.

Written by Marek's agent for Mirela's slice (agreed 16 Oct 20:22); Mirela reviews.
  1. other parcel today: the holding's parcels needing the same operation, ranked by today's status and priority
  2. lower load: load 75 % then 50 % (recomputes the axle load class)
  3. other day: first GO (else CAUTION) day in the next 3 days for the same parcel and load
Each plan carries its own cost from engine.cost (spec 7.15): working today costs EUR 0 extra; waiting until another
day costs the season_cost difference of skipping the days in between (replay year, farm level).
"""
from __future__ import annotations

import pandas as pd

from engine import params as prm

RANK = {"GO": 0, "CAUTION": 1, "NO-GO": 2}
NA = "not available"
LOAD_STEPS = (75, 50)            # spec 7.8
DAYS_AHEAD = 3                   # spec 7.8
ORIGIN = "real+synthetic+assumption"


def _better(status: str, than: str) -> bool:
    return status in RANK and than in RANK and RANK[status] < RANK[than]


def safer_plan(parcel_id: str, date, machine_id: str = "M2", load_pct: float = 100, passes: int = 1,
               operation: str = "sowing") -> list[dict]:
    from engine import data, season
    from engine.cost import wait_cost
    from engine.today import today
    d = pd.Timestamp(date)
    base = today(parcel_id, d, machine_id, load_pct, passes, operation)
    if base["status"] not in RANK or base["status"] == "GO":
        return []
    farm = data.load_farm(prm.DEMO["holding_id"].value)
    pool = farm[farm.crop.isin(season.autumn_crops())] if operation == "sowing" else farm
    pr = season.priority(pool).set_index("parcel_id")
    plans = []

    # 1. other parcel today
    cands = []
    for pid in pr.index:
        if pid == parcel_id:
            continue
        t = today(pid, d, machine_id, load_pct, passes, operation)
        if _better(t["status"], base["status"]):
            cands.append((RANK[t["status"]], pr.loc[pid, "rank"], pid, t))
    cands.sort(key=lambda c: (c[0], c[1]))
    if cands:
        _, _, pid, t = cands[0]
        row = pr.loc[pid]
        plans.append({"lever": "other parcel today", "parcel_id": pid, "date": d, "load_pct": load_pct,
                      "machine_id": machine_id, "status": t["status"],
                      "reason": f"{pid} ({row.crop}, clay {row.clay_pct:.0f}%, sand {farm.set_index('parcel_id').loc[pid, 'sand_pct']:.0f}%) "
                                f"is {t['status']} today with the same machine",
                      "alternatives": [{"parcel_id": c[2], "status": c[3]["status"]} for c in cands[1:3]],
                      "cost": {"eur": 0.0, "note": "work continues today", "origin": ORIGIN}})

    # 2. lower load
    for load in LOAD_STEPS:
        if load >= load_pct:
            continue
        t = today(parcel_id, d, machine_id, load, passes, operation)
        if _better(t["status"], base["status"]):
            plans.append({"lever": "lighter load", "parcel_id": parcel_id, "date": d, "load_pct": load,
                          "machine_id": machine_id, "status": t["status"],
                          "reason": f"{load}% load -> axle {t['axle_load_t']} t, class {t['load_class']} "
                                    f"(was {base['load_class']})",
                          "cost": {"eur": 0.0, "note": "same day; more refills not costed", "origin": ORIGIN}})
            break

    # 3. other day (first GO, else first better status, within the next 3 days)
    best = None
    for k in range(1, DAYS_AHEAD + 1):
        dd = d + pd.Timedelta(days=k)
        t = today(parcel_id, dd, machine_id, load_pct, passes, operation)
        if t["status"] == "GO":
            best = (dd, t)
            break
        if best is None and _better(t["status"], base["status"]):
            best = (dd, t)
    if best is not None:
        dd, t = best
        skipped = list(pd.date_range(d, dd - pd.Timedelta(days=1)))
        try:
            p = season.resolve_params({"machine_id": machine_id})
            b = season.season(p, years=[d.year])
            s = season.season(p, years=[d.year], skip_dates=skipped)
            from engine.cost import _econ_params, season_cost
            ep = _econ_params({}) | {"years": [d.year]}
            c0 = season_cost(b["schedule"], farm, ep)["per_year"]["total_default"].iloc[0]
            c1 = season_cost(s["schedule"], farm, ep)["per_year"]["total_default"].iloc[0]
            eur = round(float(c1 - c0), 0)
        except Exception:                                    # cost is optional for the plan; never block it
            eur = NA
        plans.append({"lever": "other day", "parcel_id": parcel_id, "date": dd, "load_pct": load_pct,
                      "machine_id": machine_id, "status": t["status"],
                      "reason": f"{dd:%d %b}: {t['status']} for the same parcel and load",
                      "cost": {"eur": eur, "note": f"waiting {len(skipped)} day(s), whole farm, replay year",
                               "origin": ORIGIN}})

    plans.sort(key=lambda p: RANK[p["status"]])
    for i, p in enumerate(plans):
        p["recommended"] = i == 0
    return plans
