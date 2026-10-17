"""Acceptance cases for engine/cost.py (owner: Mirela). Cases written by Marek (spec 6.8, 7.5, 7.15, 11.4 tests 8-11).

Skipped until engine/cost.py exists. Contract: season_cost(schedule, parcels, params) -> dict(per_year, median,
worst_year, origin); per_year has <part>_<rate> columns, part in total / late_start / weather, rate in
low / default / high (as in engine/stubs.py). If your params keys differ, change only cost_of() below.
schedule = engine.season output: parcel_id, year, date, ha_done, completion_date.
"""
import numpy as np
import pandas as pd
import pytest

cost = pytest.importorskip("engine.cost")
NA = "not available"
PARCELS = pd.DataFrame({"parcel_id": ["B", "W"], "crop": ["BARL", "COWT"], "area_ha": [10.0, 10.0]})


def schedule(barley_done, wheat_done, year=2016):
    rows = [("B", year, pd.Timestamp(barley_done), 10.0, pd.Timestamp(barley_done)),
            ("W", year, pd.Timestamp(wheat_done), 10.0, pd.Timestamp(wheat_done))]
    return pd.DataFrame(rows, columns=["parcel_id", "year", "date", "ha_done", "completion_date"])


def cost_of(sched, yield_t=5.0, price=200.0):
    params = {"yield_t_ha": {"BARL": yield_t, "COWT": yield_t}, "price_eur_t": {"BARL": price, "COWT": price}}
    return cost.season_cost(sched, PARCELS, params)


def total(res, rate="default", year=2016):
    v = res["per_year"].set_index("year").loc[year, f"total_{rate}"]
    return v


def test_8_zero_inside_the_optimal_window():
    # optimum_end: barley 20 Sep, wheat 1 Oct (params.COST), no grace
    assert total(cost_of(schedule("2016-09-20", "2016-10-01"))) == 0


def test_formula_example_one_percent_per_day():
    # barley 10 days late: 10% x 5 t/ha x 10 ha x EUR 200 = EUR 1,000; wheat on time
    res = cost_of(schedule("2016-09-30", "2016-10-01"))
    assert total(res, "low") == pytest.approx(500) and total(res) == pytest.approx(1000)
    assert total(res, "high") == pytest.approx(1500)


def test_9_higher_rate_never_lowers_cost_and_cap_holds():
    for d in ("2016-09-25", "2016-10-15", "2016-11-30"):
        res = cost_of(schedule(d, d))
        assert total(res, "low") <= total(res, "default") <= total(res, "high")
    capped = cost_of(schedule("2016-12-31", "2016-12-31"))                  # > 40 days late at any rate
    assert total(capped, "high") == pytest.approx(2 * 0.40 * 5 * 10 * 200)


def test_10_earlier_completion_never_costs_more():
    late, early = cost_of(schedule("2016-10-20", "2016-10-22")), cost_of(schedule("2016-10-12", "2016-10-13"))
    assert total(early) <= total(late)


def test_11_missing_yield_or_price_is_not_available_never_zero():
    for res in (cost_of(schedule("2016-10-20", "2016-10-22"), yield_t=None),
                cost_of(schedule("2016-10-20", "2016-10-22"), price=None)):
        v = total(res)
        assert v == NA, v


# ---------------------------------------------------------------- real data (spec 10, pre-event numbers)
@pytest.mark.needs_data
def test_real_wait_cost_demo_day_and_no_go_day():
    w = cost.wait_cost("2016-10-13", {})
    assert 500 <= w["eur"] <= 1100      # FC at -10 kPa (17 Oct): ~EUR 790; pre-event (FC -33 kPa) ~EUR 1.7k
    assert cost.wait_cost("2016-10-15", {})["eur"] == 0                       # nothing workable: waiting is free


# ---------------------------------------------------------------- test 12 (Add-on 3, spec 6.8.3)
def test_12_entry_cost_zero_when_go_and_no_go_at_least_caution():
    kw = dict(params={"yield_t_ha": {"BARL": 5.0}, "price_eur_t": {"BARL": 200.0}})
    assert cost.entry_cost("GO", "L5", "BARL", 10.0, **kw)["eur"] == 0
    for cls in ("L1", "L2", "L3", "L4", "L5"):
        assert cost.entry_cost("NO-GO", cls, "BARL", 10.0, **kw)["eur"] >= cost.entry_cost("CAUTION", cls, "BARL", 10.0, **kw)["eur"]
    # L5 NO-GO: 15% x 30% trafficked x 10 ha x 5 t x EUR 200
    assert cost.entry_cost("NO-GO", "L5", "BARL", 10.0, **kw)["eur"] == pytest.approx(0.15 * 0.3 * 10 * 5 * 200)
    assert cost.entry_cost("NO-GO", "L2", "BARL", 10.0, **kw)["eur"] == 0                   # light drill: not counted


def test_12_entry_cost_missing_price_is_not_available():
    r = cost.entry_cost("NO-GO", "L5", "XXXX", 10.0, params={"yield_t_ha": {"XXXX": 5.0}, "price_eur_t": {}})
    assert r["eur"] == NA
