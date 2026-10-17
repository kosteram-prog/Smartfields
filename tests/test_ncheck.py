"""Tests for engine/ncheck.py (written before the code; spec 6.5, 6.7, 7.10)."""
import pandas as pd
import pytest

from engine import ncheck


def wx(rain=None, tmax=10.0, start="2021-04-25", days=30):
    w = pd.DataFrame({"date": pd.date_range(start, periods=days)})
    w["precip_mm"], w["tmax_c"] = 1.0, tmax                     # 1 mm/day: 10 mm in 10 days -> no dry rule
    for d, mm in (rain or {}).items():
        w.loc[w.date == d, "precip_mm"] = mm
    return w


def test_heavy_rain_within_0_3_days_is_high_with_range():
    r = ncheck.n_check("2021-05-02", 60.0, wx({"2021-05-04": 25.0}))
    assert r["risk"] == "high" and r["n_at_risk_kg_ha"] == pytest.approx((12.0, 18.0))
    assert "25" in r["reason"]


def test_heavy_rain_on_the_application_day_counts():
    assert ncheck.n_check("2021-05-02", 60.0, wx({"2021-05-02": 30.8}))["risk"] == "high"


def test_heavy_rain_on_day_4_does_not_count():
    assert ncheck.n_check("2021-05-02", 60.0, wx({"2021-05-06": 30.0}))["risk"] == "low"


def test_dry_ten_days_is_medium():
    w = wx()
    w["precip_mm"] = 0.0
    r = ncheck.n_check("2021-05-02", 60.0, w)
    assert r["risk"] == "medium" and r["n_at_risk_kg_ha"] == pytest.approx((6.0, 9.0))


def test_frozen_soil_and_closed_period_are_prohibited():
    assert ncheck.n_check("2021-05-02", 60.0, wx(tmax=-1.0))["risk"] == "prohibited"
    r = ncheck.n_check("2021-12-10", 60.0, wx(start="2021-12-01"))
    assert r["risk"] == "prohibited" and "closed period" in r["reason"]
    assert r["n_at_risk_kg_ha"] == "not applicable"


def test_missing_weather_window_is_not_available():
    r = ncheck.n_check("2021-05-20", 60.0, wx())                # window runs past the weather table
    assert r["risk"] == "not available"


def test_no_nitrogen_is_not_applicable():
    assert ncheck.n_check("2021-05-02", 0.0, wx())["risk"] == "not applicable"


@pytest.mark.needs_data
@pytest.mark.parametrize("day,expected", [("2021-05-02", "high"), ("2019-03-29", "medium"), ("2017-03-04", "low")])
def test_real_demo_examples(day, expected):
    from engine import data
    r = ncheck.n_check(day, 60.0, data.load_weather("PL415"))
    assert r["risk"] == expected


@pytest.mark.needs_data
def test_real_spring_counts_match_pre_event_test():
    from engine import data
    f = data.load_operations("fertilisation", "FARM-13525")
    m = f[(f.product_type == "MINERAL") & (f.n_kg_ha > 0) & f.app_date.dt.month.isin([3, 4, 5])
          & f.app_date.dt.year.between(2017, 2024)]
    wxr = data.load_weather("PL415")
    risks = pd.Series([ncheck.n_check(r.app_date, r.n_kg_ha, wxr)["risk"] for r in m.itertuples()])
    assert len(m) == 127 and (risks == "high").sum() == 1 and (risks == "medium").sum() == 33
