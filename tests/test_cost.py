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


def test_formula_example_barley_rate_per_day():
    # decision 17 Oct: crop-specific rates. Barley 10 days late at 0.43 %/day (Green et al. 1985):
    # 4.3% x 5 t/ha x 10 ha x EUR 200 = EUR 430 (low 0.3 -> 300, high 0.6 -> 600); wheat on time
    res = cost_of(schedule("2016-09-30", "2016-10-01"))
    assert total(res, "low") == pytest.approx(300) and total(res) == pytest.approx(430)
    assert total(res, "high") == pytest.approx(600)


def test_wheat_keeps_one_percent_per_day_and_explicit_rates_override_all_crops():
    res = cost_of(schedule("2016-09-20", "2016-10-11"))                     # wheat 10 days late, barley on time
    assert total(res, "low") == pytest.approx(500) and total(res) == pytest.approx(1000)
    assert total(res, "high") == pytest.approx(1500)
    params = {"yield_t_ha": {"BARL": 5.0, "COWT": 5.0}, "price_eur_t": {"BARL": 200.0, "COWT": 200.0},
              "rates": {"low": 0.5, "default": 1.0, "high": 1.5}}
    res = cost.season_cost(schedule("2016-09-30", "2016-10-01"), PARCELS, params)
    assert total(res) == pytest.approx(1000)                                 # the user's own rate for every crop


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


# ---------------------------------------------------------------- long-term subsoil part (decision 17 Oct, RECARE)
KW = dict(params={"yield_t_ha": {"BARL": 5.0}, "price_eur_t": {"BARL": 200.0}})


def test_persistent_subsoil_part_for_heavy_traffic_on_wet_soil():
    pers = cost.prm.WET_TRAFFIC_LOSS["persistent"]
    rate, years = pers["pct_per_year"].value, pers["years"].value
    assert rate == 6 and years == 10
    e = cost.entry_cost("NO-GO", "L5", "BARL", 10.0, **KW)
    per_year = rate / 100 * 0.3 * 10 * 5 * 200
    assert e["persistent_eur_per_year"] == pytest.approx(per_year)
    assert e["persistent_eur_total"] == pytest.approx(per_year * years) and e["persistent_years"] == years
    assert cost.entry_cost("CAUTION", "L5", "BARL", 10.0, **KW)["persistent_eur_per_year"] == pytest.approx(per_year / 2)
    assert cost.entry_cost("NO-GO", "L4", "BARL", 10.0, **KW)["persistent_eur_per_year"] == pytest.approx(per_year / 2)
    assert cost.entry_cost("NO-GO", "L3", "BARL", 10.0, **KW)["persistent_eur_per_year"] == 0
    assert cost.entry_cost("GO", "L5", "BARL", 10.0, **KW)["persistent_eur_per_year"] == 0


def test_persistent_part_with_tyres_follows_the_subsoil_class():
    pers = cost.prm.WET_TRAFFIC_LOSS["persistent"]
    per_year = pers["pct_per_year"].value / 100 * 0.3 * 10 * 5 * 200
    red = {"assessed": True, "subsoil": "red", "overall": "red", "cost_row": "NO-GO"}
    yellow = {"assessed": True, "subsoil": "yellow", "overall": "red", "cost_row": "CAUTION"}
    green = {"assessed": True, "subsoil": "green", "overall": "yellow", "cost_row": "GO"}
    assert cost.entry_cost_tyre(red, "L2", "BARL", 10.0, **KW)["persistent_eur_per_year"] == pytest.approx(per_year)
    assert cost.entry_cost_tyre(yellow, "L2", "BARL", 10.0, **KW)["persistent_eur_per_year"] == pytest.approx(per_year / 2)
    assert cost.entry_cost_tyre(green, "L5", "BARL", 10.0, **KW)["persistent_eur_per_year"] == 0


def test_persistent_part_missing_price_is_not_available():
    r = cost.entry_cost("NO-GO", "L5", "XXXX", 10.0, params={"yield_t_ha": {"XXXX": 5.0}, "price_eur_t": {}})
    assert r["persistent_eur_per_year"] == NA and r["persistent_eur_total"] == NA


def test_12_entry_cost_missing_price_is_not_available():
    r = cost.entry_cost("NO-GO", "L5", "XXXX", 10.0, params={"yield_t_ha": {"XXXX": 5.0}, "price_eur_t": {}})
    assert r["eur"] == NA


# ---------------------------------------------------------------- avoidable losses card (17 Oct)
def test_avoidable_counts_only_bad_days_and_worst_operation_per_parcel_year():
    farm = pd.DataFrame({"parcel_id": ["A", "B"], "crop": ["BARL", "BARL"], "area_ha": [10.0, 10.0]})
    econ = {"yield_t_ha": {"BARL": 5.0}, "price_eur_t": {"BARL": 200.0}}
    ops = pd.DataFrame({"date": pd.to_datetime(["2020-05-01", "2020-06-01", "2020-07-01", "2020-07-02"]),
                        "parcel_id": ["A", "A", "A", "B"], "status": ["NO-GO", "CAUTION", "GO", "NO-GO"],
                        "load_class": ["L5", "L5", "L5", "L2"]})
    out = cost.avoidable_from_ops(ops, farm, econ).set_index("year")
    l5 = cost.entry_cost("NO-GO", "L5", "BARL", 10.0, econ)
    assert out.loc[2020, "year1_eur"] == pytest.approx(l5["eur"])                  # A: worst of NO-GO and CAUTION
    assert out.loc[2020, "subsoil_eur_per_year"] == pytest.approx(l5["persistent_eur_per_year"])
    assert out.loc[2020, "n_operations"] == 3                                     # GO day not counted


@pytest.mark.needs_data
def test_real_avoidable_losses_demo_farm():
    a = cost.avoidable_losses("FARM-13525")
    assert 8000 <= a["year1_eur_mean"] <= 13000 and 2500 <= a["subsoil_eur_per_year_mean"] <= 5000
    assert a["years"] == list(range(2017, 2025))


# ---------------------------------------------------------------- continuous go-now model (17 Oct evening)
ECON = {"yield_t_ha": {"BARL": 5.0}, "price_eur_t": {"BARL": 200.0}, "trafficked_share": 0.3}


def _g(status="NO-GO", rwc=1.05, axle=5.0, lc="L2", bar=None, clay=30.0):
    return cost.go_now_cost(status, rwc, axle, lc, clay, 30.0, 2.0, "BARL", 10.0, bar, 1, ECON)


def test_go_now_is_zero_on_go_and_positive_for_light_machines_on_wet_soil():
    assert _g("GO", 0.85)["eur"] == 0 and _g("GO", 0.85)["persistent_eur_per_year"] == 0
    e = _g("NO-GO", 1.05, 5.0, "L2")                       # the old table gave EUR 0 for L2
    assert e["eur"] > 0 and e["loss_pct"] > 0


def test_go_now_rises_with_wetness_axle_load_and_tyre_pressure():
    assert _g(rwc=1.08)["eur"] > _g(rwc=0.98)["eur"]
    assert _g(axle=8.0, lc="L3")["eur"] > _g(axle=5.0, lc="L2")["eur"] > _g(axle=3.0, lc="L1")["eur"]
    assert _g(bar=2.0)["eur"] > _g(bar=1.0)["eur"]
    assert _g(axle=13.0, lc="L5")["persistent_eur_per_year"] > _g(axle=5.0, lc="L2")["persistent_eur_per_year"]


def test_go_now_anchor_is_hakansson_15_percent():
    e = _g("NO-GO", 1.10, 11.0, "L5", bar=2.0)
    assert e["loss_pct"] == pytest.approx(15.0)
    assert e["eur"] == pytest.approx(15 / 100 * 0.3 * 10 * 5 * 200)


def test_rain_no_go_counts_even_below_the_go_limit():
    from engine import params as prm
    assert _g("NO-GO", 0.70)["drivers"]["wetness"] == prm.GO_NOW_MODEL["status_floor"].value["NO-GO"]


def test_go_or_wait_verdict():
    assert cost.go_or_wait({"eur": 100.0, "persistent_eur_total": 0.0}, {"eur": 800.0})["verdict"] == "go"
    assert cost.go_or_wait({"eur": 500.0, "persistent_eur_total": 900.0}, {"eur": 800.0})["verdict"] == "wait"
    assert cost.go_or_wait({"eur": 400.0, "persistent_eur_total": 400.0}, {"eur": 800.0})["verdict"] == "close"
    assert cost.go_or_wait({"eur": 100.0}, {"eur": "not available"})["verdict"] == "not available"


def test_day_plan_fills_capacity_with_go_plots_first_then_cheapest_wet():
    plots = pd.DataFrame({"parcel_id": ["G", "A", "B"], "status": ["GO", "CAUTION", "NO-GO"],
                          "area_ha": [10.0, 10.0, 10.0], "year1_eur": [0.0, 100.0, 500.0],
                          "subsoil_eur_total": [0.0, 0.0, 500.0]})
    assert cost.day_plan_cost(plots, 8.0, 800.0)["verdict"] == "go_plots_only"
    d = cost.day_plan_cost(plots, 15.0, 800.0)                 # 10 ha GO + 5 ha of the cheapest wet plot A
    assert d["wet_ha"] == 5.0 and d["wet_plan"][0]["parcel_id"] == "A" and d["wet_eur"] == 50.0
    assert d["wait_part_eur"] == pytest.approx(800 * 5 / 15, abs=1) and d["verdict"] == "fill_with_wet"
    d2 = cost.day_plan_cost(plots.assign(year1_eur=[0.0, 2000.0, 2000.0]), 15.0, 800.0)
    assert d2["verdict"] == "go_plots_only_wait"
