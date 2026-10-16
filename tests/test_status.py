"""Acceptance cases for engine/status.py (owner: Mirela). Cases written by Marek (cross-written, split 2.3).

Spec 6.4, 7.3, 11.4 test 3 + the 13 Oct 2016 demo constants. Skipped until engine/status.py exists.
Contract: classify_day(rwc_eff, clay_pct, sand_pct, rain_today_mm, rain_prev24h_mm, tmax_c, load_class,
          passes=1, operation="sowing") -> dict(status, access, suitability, risk 0-100, reasons[list of str])
          status_table(soil_water_df, parcels, load_class, passes=1, operation="sowing") -> df + status, risk, reasons
          axle_load_class(machine_id, load_pct) -> (load_class "L1".."L5", axle load t)
"""
import numpy as np
import pandas as pd
import pytest

status = pytest.importorskip("engine.status")

RANK = {"GO": 0, "CAUTION": 1, "NO-GO": 2}
LOAM = dict(clay_pct=20.0, sand_pct=40.0)        # no texture adjustment
DRY = dict(rain_today_mm=0.0, rain_prev24h_mm=0.0, tmax_c=12.0)


def day(rwc, cls="L2", passes=1, operation="sowing", **kw):
    args = {**LOAM, **DRY, **kw}
    return status.classify_day(rwc, args["clay_pct"], args["sand_pct"], args["rain_today_mm"],
                               args["rain_prev24h_mm"], args["tmax_c"], cls, passes, operation)


# ---------------------------------------------------------------- test 3 (spec 11.4)
@pytest.mark.parametrize("cls", ["L1", "L2", "L3", "L4", "L5"])
def test_5_mm_rain_today_is_no_go_for_any_machine(cls):
    r = day(0.30, cls, rain_today_mm=5.0)
    assert r["status"] == "NO-GO" and any("rain" in x.lower() for x in r["reasons"])


def test_heavier_class_is_never_less_strict():
    for rwc in np.arange(0.60, 1.25, 0.01):
        ranks = [RANK[day(rwc, c)["status"]] for c in ("L1", "L2", "L3", "L4", "L5")]
        assert ranks == sorted(ranks), (round(rwc, 2), ranks)


def test_wetter_soil_is_never_better():
    for cls in ("L1", "L2", "L3", "L4", "L5"):
        ranks = [RANK[day(rwc, cls)["status"]] for rwc in np.arange(0.60, 1.25, 0.01)]
        assert ranks == sorted(ranks)


# ---------------------------------------------------------------- table 6.4 + texture + overrides
@pytest.mark.parametrize("rwc,expected", [(0.95, "GO"), (0.96, "CAUTION"), (1.05, "CAUTION"), (1.06, "NO-GO")])
def test_l2_thresholds_on_loam(rwc, expected):
    assert day(rwc, "L2")["status"] == expected


def test_texture_adjustment():
    assert day(0.92, "L2", clay_pct=30.0, sand_pct=20.0)["status"] == "CAUTION"   # clay >= 30%: GO <= 0.90
    assert day(0.99, "L2", clay_pct=5.0, sand_pct=70.0)["status"] == "GO"         # sand >= 70%: GO <= 1.00


def test_clay_at_field_capacity_with_light_drill_is_caution():                     # agreed decision A1
    assert day(1.00, "L2", clay_pct=45.0, sand_pct=20.0)["status"] == "CAUTION"


def test_rain_previous_24h_caps_at_caution():
    assert day(0.50, "L2", rain_prev24h_mm=10.0)["status"] == "CAUTION"
    assert day(0.50, "L2", rain_prev24h_mm=9.9)["status"] == "GO"


def test_frozen_soil_carries_light_traffic_but_never_fertilising():
    assert day(1.20, "L2", tmax_c=-1.0)["status"] == "GO"            # NO-GO only because of RWC -> GO when frozen
    assert day(1.20, "L5", tmax_c=-1.0)["status"] == "NO-GO"         # L4-L5 not covered by the frost rule
    assert day(0.50, "L2", tmax_c=-1.0, operation="fertilising")["status"] == "NO-GO"


def test_each_extra_pass_tightens_thresholds_by_0_03():
    assert day(0.94, "L2", passes=1)["status"] == "GO"
    assert day(0.94, "L2", passes=2)["status"] == "CAUTION"          # GO <= 0.92 with two passes


def test_risk_score_range_and_order():
    r = [day(x, "L2")["risk"] for x in (0.5, 0.9, 1.0, 1.1)]
    assert all(0 <= v <= 100 for v in r) and r == sorted(r)
    assert day(0.30, "L2", rain_today_mm=8.0)["risk"] >= 65            # override forces NO-GO risk
    assert isinstance(day(0.9)["reasons"], list) and all(isinstance(x, str) for x in day(0.9)["reasons"])


@pytest.mark.parametrize("machine,load,expected", [("M2", 100, "L2"), ("M3", 100, "L3"), ("M5", 100, "L5"),
                                                   ("M1", 0, "L1")])
def test_axle_load_class(machine, load, expected):
    assert status.axle_load_class(machine, load)[0] == expected


def test_status_table_matches_classify_day_row_by_row():
    sw = pd.DataFrame({"parcel_id": ["A", "A", "B"], "date": pd.to_datetime(["2016-10-13"] * 3),
                       "RWC_eff": [0.80, 1.00, 1.08], "rain_today_mm": [0.0, 6.0, 0.0],
                       "rain_prev24h_mm": [0.0, 0.0, 12.0], "tmax_c": [10.0, 10.0, 10.0]})
    parcels = pd.DataFrame({"parcel_id": ["A", "B"], "clay_pct": [45.0, 8.0], "sand_pct": [20.0, 75.0]})
    out = status.status_table(sw, parcels, "L2")
    assert len(out) == 3 and {"status", "risk", "reasons"} <= set(out.columns)
    for r, s in zip(sw.itertuples(), out.status):
        p = parcels.set_index("parcel_id").loc[r.parcel_id]
        assert s == status.classify_day(r.RWC_eff, p.clay_pct, p.sand_pct, r.rain_today_mm, r.rain_prev24h_mm,
                                        r.tmax_c, "L2")["status"]


# ---------------------------------------------------------------- demo (spec 10, pre-event table)
EXPECTED = {   # date: (0149869 clay 55%, 0149906 sand 78%, 0149917 clay 39%) as "L2/L3"
    "2016-10-08": ("NO-GO/NO-GO", "CAUTION/CAUTION", "NO-GO/NO-GO"),
    "2016-10-12": ("NO-GO/NO-GO", "CAUTION/CAUTION", "NO-GO/NO-GO"),
    "2016-10-13": ("CAUTION/NO-GO", "GO/CAUTION", "CAUTION/NO-GO"),
    "2016-10-14": ("CAUTION/CAUTION", "GO/GO", "CAUTION/CAUTION"),
    "2016-10-15": ("NO-GO/NO-GO", "NO-GO/NO-GO", "NO-GO/NO-GO"),
    "2016-10-17": ("CAUTION/NO-GO", "GO/CAUTION", "CAUTION/NO-GO"),
}


@pytest.mark.needs_data
def test_real_october_2016_demo_statuses():
    from engine import data, soil
    farm = data.load_farm("FARM-13525")
    farm = farm[farm.parcel_id.isin(["PARCEL-0149869", "PARCEL-0149906", "PARCEL-0149917"])]
    sw = soil.soil_water(farm, data.load_weather("PL415"))
    sw = sw[sw.date.isin(pd.to_datetime(list(EXPECTED)))]
    l2 = status.status_table(sw, farm, "L2").set_index(["date", "parcel_id"]).status
    l3 = status.status_table(sw, farm, "L3").set_index(["date", "parcel_id"]).status
    for d, exp in EXPECTED.items():
        got = tuple(f"{l2[(pd.Timestamp(d), p)]}/{l3[(pd.Timestamp(d), p)]}"
                    for p in ("PARCEL-0149869", "PARCEL-0149906", "PARCEL-0149917"))
        assert got == exp, (d, got, exp)
