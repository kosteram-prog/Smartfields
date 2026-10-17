"""Tests for engine/today.py (written before the code; spec 7.7, 7.9 and the 13 Oct 2016 demo cases)."""
import pandas as pd
import pytest

from engine import today as td

PARCEL = pd.Series({"parcel_id": "P1", "crop": "BARL", "area_ha": 7.6, "clay_pct": 20.0, "sand_pct": 40.0})


def inputs(rwc=(0.80, 0.80, 0.80, 0.80), rain=(0, 0, 0, 0), tmax=(12, 12, 12, 12), wind=(2, 2, 2, 2)):
    dates = pd.date_range("2016-10-12", periods=len(rwc))
    sw = pd.DataFrame({"parcel_id": "P1", "date": dates, "W_mm": 50.0, "RWC": list(rwc), "RWC_eff": list(rwc),
                       "rain_today_mm": list(rain), "rain_prev24h_mm": [0] + list(rain[:-1]),
                       "rain_prev48h_mm": [r + p for r, p in zip(rain, [0] + list(rain[:-1]))], "tmax_c": list(tmax)})
    wx = pd.DataFrame({"date": dates, "precip_mm": list(rain), "et0_mm": 1.0, "tmin_c": [t - 8 for t in tmax],
                       "tmean_c": [t - 4 for t in tmax], "tmax_c": list(tmax), "wind_m_s": list(wind)})
    return sw, wx


def run(date="2016-10-13", machine="M2", load=100, passes=1, operation="sowing", observation=None, **kw):
    sw, wx = inputs(**kw)
    return td.assess(sw, wx, PARCEL, date, machine, load, passes, operation, observation=observation)


def test_contract_keys_and_conditions():
    r = run()
    for k in ["access", "suitability", "status", "strip72", "reasons", "confidence", "based_on", "missing",
              "best_next_check", "conditions", "origin"]:
        assert k in r, k
    assert set(r["conditions"]) >= {"rwc_eff", "precip_mm", "precip_last48h_mm", "tmin_c", "tmax_c", "wind_m_s"}
    assert r["status"] == "GO" and r["access"] == "GO" and r["suitability"] == "GO"


def test_strip72_is_today_plus_two_days():
    r = run()
    assert [s["date"] for s in r["strip72"]] == [pd.Timestamp(f"2016-10-{d}") for d in (13, 14, 15)]
    assert all(s["status"] == "GO" for s in r["strip72"])


def test_strip_beyond_weather_is_not_available():
    r = run(date="2016-10-14")                                 # weather ends 15 Oct
    assert r["strip72"][2]["status"] == "not available"


def test_overall_status_is_the_worse_of_access_and_suitability():
    r = run(rain=(0, 2, 0, 0))                                  # 2 mm today: access fine, sowing in rain is not
    assert r["access"] == "GO" and r["suitability"] == "CAUTION" and r["status"] == "CAUTION"
    assert any("rain" in x.lower() for x in r["reasons"])


def test_wet_soil_drives_access():
    r = run(rwc=(1.2, 1.2, 1.2, 1.2))
    assert r["access"] == "NO-GO" and r["status"] == "NO-GO"


def test_fertilising_on_frozen_soil_is_no_go():
    r = run(operation="fertilising", tmax=(-2, -2, -2, -2))
    assert r["suitability"] == "NO-GO" and r["status"] == "NO-GO"


def test_spraying_in_wind_is_caution():
    r = run(operation="spraying", wind=(6, 6, 6, 6))
    assert r["suitability"] == "CAUTION"


def test_confidence_spec_7_9():
    base = run()["confidence"]
    assert base == 100 - 20 - 15 - 10 - 5 - 5                   # regional weather, synthetic soil, default machine, replay, no observation
    assert run(observation="ball test: crumbles")["confidence"] == base + 5
    assert run(load=None)["confidence"] == base - 5 and run(passes=None)["confidence"] == base - 5
    assert "Farmer observation" in " ".join(run()["missing"])


def test_days_to_first_go():
    assert run()["days_to_first_go"] == 0
    assert run(rwc=(0.8, 1.2, 1.2, 0.8))["days_to_first_go"] == 2
    assert run(rwc=(0.8, 1.2, 1.2, 1.2))["days_to_first_go"] == "beyond 72 h"


def test_date_without_weather_is_not_available_not_a_guess():
    r = run(date="2017-05-01")
    assert r["status"] == "not available" and r["confidence"] == "not available"


# ---------------------------------------------------------------- real data: demo cases (spec 10)
@pytest.mark.needs_data
@pytest.mark.parametrize("parcel,machine,day,expected", [
    ("PARCEL-0149869", "M3", 13, "NO-GO"),
    ("PARCEL-0149869", "M2", 13, "CAUTION"),
    ("PARCEL-0149906", "M2", 13, "GO"),
    ("PARCEL-0149869", "M3", 14, "CAUTION"),
])
def test_real_demo_cases(parcel, machine, day, expected):
    r = td.today(parcel, f"2016-10-{day}", machine, 100, 1, "sowing")
    assert r["status"] == expected, r["reasons"]


@pytest.mark.needs_data
def test_real_unknown_parcel_raises():
    with pytest.raises(ValueError):
        td.today("PARCEL-9999999", "2016-10-13", "M2", 100, 1, "sowing")


def test_custom_machine_uses_its_axle_load_and_raises_confidence():
    sw, wx = inputs()
    base = td.assess(sw, wx, PARCEL, "2016-10-13", "M2", 100, 1, "sowing")
    r = td.assess(sw, wx, PARCEL, "2016-10-13", "M2", 100, 1, "sowing",
                  custom_machine={"name": "My JD 6R + 4 m drill", "axle_t": 9.0})
    assert r["load_class"] == "L4" and r["axle_load_t"] == 9.0
    assert r["confidence"] == base["confidence"] + 10


def test_seven_day_outlook_starts_with_the_72h_strip():
    sw, wx = inputs(rwc=(0.8,) * 10, rain=(0,) * 10, tmax=(12,) * 10, wind=(2,) * 10)
    r = td.assess(sw, wx, PARCEL, "2016-10-13", "M2", 100, 1, "sowing")
    assert len(r["outlook7"]) == 7 and r["outlook7"][:3] == r["strip72"]
    assert r["days_to_first_go_7d"] == 0
    short = run(date="2016-10-14")                        # weather ends 15 Oct: later days not available
    assert [o["status"] for o in short["outlook7"]][2:] == ["not available"] * 5
