"""Find a safer plan (spec 7.8 + lever 4 agreed 16 Oct 22:46): never worse than the input.

Written by Marek's agent for Mirela's slice; Mirela reviews.
  1. other parcel today: the holding's parcels needing the same operation, ranked by today's status and priority
  2. lighter load: load 75 % then 50 % (recomputes the axle load class)
  3. lighter machine: a lighter machine for the same operation, on the same parcel; if that is still not GO,
     also the best other parcel with that machine (the spec 10 story: M3 NO-GO -> M2 CAUTION -> sandy parcel GO)
  4. other day: first GO (else better) day in the next 3 days for the same parcel and load
Each plan carries its own cost (spec 7.15): working today costs EUR 0 extra; a slower machine costs the season
cost difference (replay year); waiting costs the season cost of skipping the days in between (farm level).
"""
from __future__ import annotations

import pandas as pd

from engine import params as prm

RANK = {"GO": 0, "CAUTION": 1, "NO-GO": 2}
CLASS_RANK = {"L1": 1, "L2": 2, "L3": 3, "L4": 4, "L5": 5}
NA = "not available"
LOAD_STEPS = (75, 50)            # spec 7.8
DAYS_AHEAD = 3                   # spec 7.8
ORIGIN = "real+synthetic+assumption"
OPERATION_WORDS = {"sowing": ("sowing", "drill"), "spraying": ("spraying",), "fertilising": ("fertiliser",)}


def _better(status: str, than: str) -> bool:
    return status in RANK and than in RANK and RANK[status] < RANK[than]


def _season_cost(year: int, params: dict, farm, skip_dates=None):
    from engine import season
    from engine.cost import _econ_params, season_cost
    res = season.season(params, years=[year], skip_dates=skip_dates)
    return season_cost(res["schedule"], farm, _econ_params({}) | {"years": [year]})["per_year"]["total_default"].iloc[0]


def _cost_diff(year, farm, base_params, other_params, skip_dates=None):
    try:
        return round(float(_season_cost(year, other_params, farm, skip_dates) - _season_cost(year, base_params, farm)), 0)
    except Exception:                    # a plan is still useful without its cost
        return NA


def lighter_machines(machine_id: str, operation: str) -> list[str]:
    """Machines for the same operation with a lighter full-load class, heaviest first (keeps the most capacity)."""
    words = OPERATION_WORDS.get(operation, ())
    base = CLASS_RANK[prm.MACHINES[machine_id]["load_class"]]
    out = [m for m, v in prm.MACHINES.items()
           if m != machine_id and CLASS_RANK[v["load_class"]] < base and any(w in v["operations"] for w in words)]
    return sorted(out, key=lambda m: -CLASS_RANK[prm.MACHINES[m]["load_class"]])


def safer_plan(parcel_id: str, date, machine_id: str = "M2", load_pct: float = 100, passes: int = 1,
               operation: str = "sowing") -> list[dict]:
    from engine import data, season
    from engine.today import today
    d = pd.Timestamp(date)
    base = today(parcel_id, d, machine_id, load_pct, passes, operation)
    if base["status"] not in RANK or base["status"] == "GO":
        return []
    farm = data.load_farm(prm.DEMO["holding_id"].value)
    pool = farm[farm.crop.isin(season.autumn_crops())] if operation == "sowing" else farm
    pr = season.priority(pool).set_index("parcel_id")
    texture = farm.set_index("parcel_id")[["clay_pct", "sand_pct"]]
    plans = []

    def best_other_parcel(machine, load, than):
        cands = []
        for pid in pr.index:
            if pid == parcel_id:
                continue
            t = today(pid, d, machine, load, passes, operation)
            if _better(t["status"], than):
                cands.append((RANK[t["status"]], pr.loc[pid, "rank"], pid, t))
        return sorted(cands, key=lambda c: (c[0], c[1]))

    def describe(pid):
        return (f"{pid} ({pr.loc[pid, 'crop'] if pid in pr.index else ''}, clay {texture.loc[pid, 'clay_pct']:.0f}%, "
                f"sand {texture.loc[pid, 'sand_pct']:.0f}%)")

    # 1. other parcel today
    cands = best_other_parcel(machine_id, load_pct, base["status"])
    if cands:
        _, _, pid, t = cands[0]
        plans.append({"lever": "other parcel today", "parcel_id": pid, "date": d, "load_pct": load_pct,
                      "machine_id": machine_id, "status": t["status"],
                      "reason": f"{describe(pid)} is {t['status']} today with the same machine",
                      "alternatives": [{"parcel_id": c[2], "status": c[3]["status"]} for c in cands[1:3]],
                      "cost": {"eur": 0.0, "note": "work continues today", "origin": ORIGIN}})

    # 2. lighter load
    for load in LOAD_STEPS:
        if load >= load_pct:
            continue
        t = today(parcel_id, d, machine_id, load, passes, operation)
        if _better(t["status"], base["status"]):
            plans.append({"lever": "lighter load", "parcel_id": parcel_id, "date": d, "load_pct": load,
                          "machine_id": machine_id, "status": t["status"],
                          "reason": f"{load}% load -> axle {t['axle_load_t']} t, class {t['load_class']} "
                                    f"(was {base['load_class']})",
                          "cost": {"eur": 0.0, "note": "same day; extra refills not costed", "origin": ORIGIN}})
            break

    # 3. lighter machine (same parcel; else the best other parcel with that machine)
    if machine_id in prm.MACHINES:
        for m in lighter_machines(machine_id, operation):
            t = today(parcel_id, d, m, 100, passes, operation)
            base_p, other_p = {"machine_id": machine_id}, {"machine_id": m}
            rate_note = (f"{prm.MACHINES[m]['rate_ha_h'].value} ha/h instead of "
                         f"{prm.MACHINES[machine_id]['rate_ha_h'].value} ha/h: slower sowing, season cost difference")
            if operation != "sowing":
                cost = {"eur": NA, "note": "slower machine; cost modelled for sowing only", "origin": ORIGIN}
            else:
                cost = {"eur": _cost_diff(d.year, farm, base_p, other_p), "note": rate_note, "origin": ORIGIN}
            if _better(t["status"], base["status"]):
                plans.append({"lever": "lighter machine", "parcel_id": parcel_id, "date": d, "load_pct": 100,
                              "machine_id": m, "status": t["status"],
                              "reason": f"{m} ({prm.MACHINES[m]['profile']}) -> class {t['load_class']}: {t['status']}",
                              "cost": cost})
            if t["status"] != "GO":
                others = best_other_parcel(m, 100, t["status"] if _better(t["status"], base["status"]) else base["status"])
                if others:
                    _, _, pid, to = others[0]
                    plans.append({"lever": "lighter machine, other parcel", "parcel_id": pid, "date": d, "load_pct": 100,
                                  "machine_id": m, "status": to["status"],
                                  "reason": f"{m} on {describe(pid)}: {to['status']} today",
                                  "alternatives": [{"parcel_id": c[2], "status": c[3]["status"]} for c in others[1:3]],
                                  "cost": cost})
            if any(p["lever"].startswith("lighter machine") for p in plans):
                break

    # 4. other day (first GO, else first better status, within the next 3 days)
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
        p = {"machine_id": machine_id if machine_id in prm.MACHINES else None}
        eur = _cost_diff(d.year, farm, p, p, skip_dates=skipped) if operation == "sowing" else NA
        plans.append({"lever": "other day", "parcel_id": parcel_id, "date": dd, "load_pct": load_pct,
                      "machine_id": machine_id, "status": t["status"],
                      "reason": f"{dd:%d %b}: {t['status']} for the same plot and load",
                      "cost": {"eur": eur, "note": f"waiting {len(skipped)} day(s), whole farm, replay year",
                               "origin": ORIGIN}})

    plans.sort(key=lambda p: (RANK[p["status"]], 0 if p["cost"]["eur"] == 0 else 1))
    for i, p in enumerate(plans):
        p["recommended"] = i == 0
    return plans
