"""Tests for engine/season.py (written before the code; spec 7.4-7.6, 11.4 test 4).

Part 1: the allocation core `simulate` on hand-made status tables (no data needed).
Part 2 (needs_data): the pre-event reference numbers for FARM-13525 (spec section 10).
"""
import datetime as dt
import time

import numpy as np
import pandas as pd
import pytest

from engine import season

YEARS = [2015, 2016]


def farm(*rows):
    rows = rows or [("A", "BARL", 10.0, 50.0), ("B", "COWT", 10.0, 10.0)]
    return pd.DataFrame(rows, columns=["parcel_id", "crop", "area_ha", "clay_pct"])


def statuses(parcels, default="GO", overrides=None, years=YEARS):
    """One row per parcel per day 1 Oct - 30 Nov; overrides = {(parcel_id, 'YYYY-MM-DD'): status}."""
    rows = []
    for y in years:
        for d in pd.date_range(f"{y}-10-01", f"{y}-11-30"):
            for pid in parcels.parcel_id:
                rows.append((pid, d, (overrides or {}).get((pid, d.strftime("%Y-%m-%d")), default)))
    return pd.DataFrame(rows, columns=["parcel_id", "date", "status"])


def done(completion, year):
    return completion.set_index("year").completion_date[year]


# ---------------------------------------------------------------- priority (7.6)
def test_priority_score_spec_7_6():
    p = pd.DataFrame({"parcel_id": ["H", "S", "W"], "crop": ["BARL", "BARL", "COWT"],
                      "area_ha": [7.61, 6.34, 9.0], "clay_pct": [54.8, 6.6, 30.0]})
    s = season.priority(p).set_index("parcel_id").priority
    assert s["H"] == 3 * 2 + 2 * 3 + 1 and s["S"] == 3 * 2 + 2 * 1 + 0 and s["W"] == 3 * 1 + 2 * 2 + 1
    assert list(season.priority(p).sort_values("rank").parcel_id) == ["H", "S", "W"]


# ---------------------------------------------------------------- test 4 (spec 11.4)
def test_infinite_capacity_gives_p_100():
    p = farm()
    sched, comp = season.simulate(statuses(p), p, own_ha_day=float("inf"), years=YEARS)
    assert season.p_by_deadline(comp, "10-15") == 1.0
    assert all(done(comp, y) == pd.Timestamp(f"{y}-10-01") for y in YEARS)


def test_zero_capacity_gives_p_0_and_not_done():
    p = farm()
    sched, comp = season.simulate(statuses(p), p, own_ha_day=0.0, years=YEARS)
    assert season.p_by_deadline(comp, "10-15") == 0.0
    assert comp.completion_date.isna().all() and sched.empty


def test_contractor_never_lowers_p_or_delays_completion():
    rng = np.random.default_rng(1)
    p = farm(*[(f"P{i}", "BARL" if i % 2 else "COWT", float(rng.uniform(3, 12)), float(rng.uniform(5, 55)))
               for i in range(12)])
    st = statuses(p)
    st["status"] = rng.choice(["GO", "CAUTION", "NO-GO"], size=len(st), p=[0.3, 0.3, 0.4])
    last = None
    for extra in (0, 5, 10, 15, 30):
        _, comp = season.simulate(st, p, own_ha_day=15.0, contractor_ha_day=extra, years=YEARS)
        cd = comp.completion_date.fillna(pd.Timestamp("2100-01-01"))
        if last is not None:
            assert (cd <= last).all()
        last = cd


# ---------------------------------------------------------------- allocation rules (7.4-7.5)
def test_perfect_weather_takes_area_over_capacity_days():
    p = farm(("A", "BARL", 78.2, 40.0), ("B", "COWT", 55.5, 10.0))      # 133.7 ha
    _, comp = season.simulate(statuses(p, default="NO-GO"), p, own_ha_day=15.0, years=YEARS, perfect_weather=True)
    assert done(comp, 2016) == pd.Timestamp("2016-10-09")               # ceil(133.7 / 15) = 9 days


def test_schedule_adds_up_to_parcel_area_and_follows_priority():
    p = farm()
    sched, _ = season.simulate(statuses(p), p, own_ha_day=4.0, years=[2016])
    assert sched.groupby("parcel_id").ha_done.sum().to_dict() == pytest.approx({"A": 10.0, "B": 10.0})
    first = sched.sort_values("date").groupby("parcel_id").completion_date.first()
    assert first["A"] < first["B"]                                        # A: barley on clay -> higher priority
    for col in ["parcel_id", "year", "date", "ha_done", "completion_date", "ha_contractor", "origin"]:
        assert col in sched.columns


def test_no_go_days_are_never_worked():
    p = farm(("A", "BARL", 10.0, 50.0))
    over = {("A", f"2016-10-0{d}"): "NO-GO" for d in range(1, 6)}
    sched, comp = season.simulate(statuses(p, overrides=over, years=[2016]), p, own_ha_day=5.0, years=[2016])
    assert sched.date.min() == pd.Timestamp("2016-10-06") and done(comp, 2016) == pd.Timestamp("2016-10-07")


def test_caution_weight_scales_productivity():
    p = farm(("A", "BARL", 10.0, 50.0))
    st = statuses(p, default="CAUTION", years=[2016])
    for w, expected in ((1.0, "2016-10-02"), (0.5, "2016-10-04")):
        _, comp = season.simulate(st, p, own_ha_day=5.0, caution_weight=w, years=[2016])
        assert done(comp, 2016) == pd.Timestamp(expected)
    _, comp = season.simulate(st, p, own_ha_day=5.0, caution_weight=0.0, years=[2016])
    assert comp.completion_date.isna().all()


def test_go_parcel_used_when_priority_parcel_is_no_go():
    p = farm()
    over = {("A", "2016-10-01"): "NO-GO"}
    sched, _ = season.simulate(statuses(p, overrides=over, years=[2016]), p, own_ha_day=5.0, years=[2016])
    day1 = sched[sched.date == "2016-10-01"]
    assert list(day1.parcel_id) == ["B"]


def test_skip_dates_never_speed_up_and_no_go_skip_changes_nothing():
    p = farm()
    over = {(pid, "2016-10-03"): "NO-GO" for pid in ("A", "B")}
    st = statuses(p, overrides=over, years=[2016])
    _, base = season.simulate(st, p, own_ha_day=4.0, years=[2016])
    _, skip_go = season.simulate(st, p, own_ha_day=4.0, years=[2016], skip_dates=["2016-10-01"])
    _, skip_nogo = season.simulate(st, p, own_ha_day=4.0, years=[2016], skip_dates=["2016-10-03"])
    assert done(skip_go, 2016) > done(base, 2016)
    assert done(skip_nogo, 2016) == done(base, 2016)


def test_contractor_starts_on_its_start_date_and_gets_its_share():
    p = farm(("A", "BARL", 40.0, 50.0))
    sched, _ = season.simulate(statuses(p, years=[2016]), p, own_ha_day=10.0, contractor_ha_day=10.0,
                               contractor_start="10-03", years=[2016])
    by_day = sched.set_index("date")
    assert by_day.loc["2016-10-01", "ha_contractor"] == 0 and by_day.loc["2016-10-03", "ha_contractor"] == pytest.approx(10.0)
    assert by_day.loc["2016-10-03", "ha_done"] == pytest.approx(20.0)    # remaining 20 ha, capacity 20


def test_workable_days_share_is_area_weighted():
    p = farm(("A", "BARL", 30.0, 50.0), ("B", "COWT", 10.0, 10.0))
    st = statuses(p, overrides={("A", "2016-10-01"): "NO-GO"}, years=[2016])
    wd = season.workable_days(st, p).set_index("date")
    assert wd.loc["2016-10-01", "share_go"] == pytest.approx(0.25) and wd.loc["2016-10-02", "share_go"] == 1.0
    assert wd.loc["2016-10-01", "share_go_parcels"] == pytest.approx(0.5)


def test_farm_without_autumn_sowing_gives_message_not_error():
    res = season.season_from_inputs(farm(("M", "MAIZ", 10.0, 20.0)), statuses(farm(("M", "MAIZ", 10.0, 20.0))), {})
    assert res["P_by_deadline"]["value"] == "not available"
    assert "No autumn sowing" in res["message"]


# ---------------------------------------------------------------- real data (needs the extracts)
# FC at -10 kPa (decision 17 Oct). Pre-event reference with FC -33 kPa: 09, 22, 16, 09, 16, 16, 10, 09, 13, 11 Oct, P 0.6
REF = ["10-09", "10-17", "10-16", "10-09", "10-15", "10-11", "10-10", "10-09", "10-13", "10-11"]


@pytest.fixture(scope="module")
def real():
    t0 = time.time()
    res = season.season({})
    return res, time.time() - t0


@pytest.mark.needs_data
def test_real_reference_completion_and_p(real):
    res, runtime = real
    comp = res["completion"].set_index("year").completion_date
    got = [comp[y].strftime("%m-%d") for y in range(2015, 2025)]
    off = [abs((pd.Timestamp(f"2000-{g}") - pd.Timestamp(f"2000-{r}")).days) for g, r in zip(got, REF)]
    assert max(off) <= 1, list(zip(range(2015, 2025), got, REF))
    assert res["P_by_deadline"]["value"] == pytest.approx(0.8)
    assert runtime < 10


@pytest.mark.needs_data
def test_real_contractor_and_sensitivity(real):
    res, _ = real
    rec = res["contractor_recommendation"]
    assert rec["extra_ha_day"] == 5 and rec["p_with"] >= 0.9
    assert res["sensitivity"][0.5] == pytest.approx(0.8) and res["sensitivity"][1.0] >= res["sensitivity"][0.0]


@pytest.mark.needs_data
def test_real_three_workable_days_early_october_2016(real):
    res, _ = real
    wd = res["workable_days"]
    oct16 = wd[(wd.date >= "2016-10-01") & (wd.date <= "2016-10-21")]
    # FC at -10 kPa (17 Oct): 8 by parcels, 7 by area (1-2 Oct and 7-11 Oct, 14 Oct). Pre-event (FC -33 kPa): 3.
    assert (oct16.share_go_parcels >= 0.5).sum() == 8
    assert (oct16.share_go >= 0.5).sum() == 7


def test_custom_parcel_order_is_followed():
    p = farm()
    sched, _ = season.simulate(statuses(p), p, own_ha_day=4.0, years=[2016], order=["B", "A"])
    first = sched.sort_values("date").groupby("parcel_id").completion_date.first()
    assert first["B"] < first["A"]


def test_fleet_adds_capacity_and_uses_the_heaviest_class():
    p = season.resolve_params({"machine_id": "M2", "units": 1, "hours": 10, "fleet": (("M3", 1),)})
    assert p["ha_per_day"] == pytest.approx(1.5 * 10 + 2.5 * 10)
    assert p["load_class"] == "L3"
    assert season.resolve_params({"machine_id": "M2"})["load_class"] == "L2"
