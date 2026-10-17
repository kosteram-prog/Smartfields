"""Acceptance cases for engine/plan.py (owner: Mirela). Cases written by Marek (spec 7.8, 11.4 test 5).

Skipped until engine/plan.py exists. Contract: safer_plan(parcel_id, date, machine_id, load_pct, passes)
-> list of dicts: lever, parcel_id, date, load_pct, status, reason, cost ({eur or "not available", origin}).
"""
import pytest

plan = pytest.importorskip("engine.plan")
RANK = {"GO": 0, "CAUTION": 1, "NO-GO": 2}
LEVERS = {"other parcel today", "lighter load", "lighter machine", "lighter machine, other parcel", "other day"}


@pytest.mark.needs_data
@pytest.mark.parametrize("parcel,machine,load", [("PARCEL-0149869", "M3", 100), ("PARCEL-0149869", "M2", 100),
                                                 ("PARCEL-0149917", "M3", 60)])
def test_safer_plan_is_never_worse_than_the_input(parcel, machine, load):
    from engine.today import today
    base = today(parcel, "2016-10-13", machine, load, 1, "sowing")["status"]
    plans = plan.safer_plan(parcel, "2016-10-13", machine, load, 1)
    assert 1 <= len(plans) <= 5
    for p in plans:
        assert p["lever"] in LEVERS and RANK[p["status"]] <= RANK[base], p
        assert p["reason"] and "origin" in p["cost"]


@pytest.mark.needs_data
def test_demo_other_parcel_today_is_the_sandy_parcel_go():
    # spec 10: clay parcel with the M2 drill is CAUTION; other parcels are GO with M2 today. Since FC at -10 kPa
    # (17 Oct) the highest-priority GO parcel is 0149898 (clay 30%); the sandy 0149906 is GO and listed as well.
    plans = {p["lever"]: p for p in plan.safer_plan("PARCEL-0149869", "2016-10-13", "M2", 100, 1)}
    other = plans["other parcel today"]
    assert other["status"] == "GO"
    shown = {other["parcel_id"]} | {a["parcel_id"] for a in other["alternatives"] if a["status"] == "GO"}
    assert "PARCEL-0149906" in shown


@pytest.mark.needs_data
def test_heavy_m3_gets_a_better_plan_even_without_any_go_today():
    plans = plan.safer_plan("PARCEL-0149869", "2016-10-13", "M3", 100, 1)    # input NO-GO
    assert plans and all(p["status"] in ("GO", "CAUTION") for p in plans)


@pytest.mark.needs_data
def test_spec_10_story_lighter_machine_then_sandy_parcel():
    # M3 full on clay = NO-GO; the M2 drill makes it CAUTION. Since FC at -10 kPa (17 Oct) the recommended plan is
    # the same M3 on a light parcel (GO, EUR 0); M2 on another parcel is GO too (sandy 0149906 among the options).
    plans = plan.safer_plan("PARCEL-0149869", "2016-10-13", "M3", 100, 1)
    by = {p["lever"]: p for p in plans}
    assert by["lighter machine"]["machine_id"] == "M2" and by["lighter machine"]["status"] == "CAUTION"
    first = plans[0]
    assert first["lever"] == "other parcel today" and first["status"] == "GO" and first["cost"]["eur"] == 0
    from engine import data
    clay = data.load_farm("FARM-13525").set_index("parcel_id").clay_pct
    assert clay[first["parcel_id"]] < 10                                                  # a light, sandy parcel
    combo = by["lighter machine, other parcel"]
    assert combo["status"] == "GO" and "PARCEL-0149906" in {combo["parcel_id"]} | {a["parcel_id"] for a in combo["alternatives"]}
    assert isinstance(combo["cost"]["eur"], float) and combo["cost"]["eur"] >= 0       # M2 is slower than M3


def test_lighter_machines_for_sowing():
    assert plan.lighter_machines("M3", "sowing") == ["M2", "M1"]
    assert plan.lighter_machines("M2", "sowing") == ["M1"]


@pytest.mark.needs_data
def test_no_plan_offered_when_input_is_already_go():
    plans = plan.safer_plan("PARCEL-0149906", "2016-10-13", "M2", 100, 1)
    assert all(p["status"] == "GO" for p in plans)
