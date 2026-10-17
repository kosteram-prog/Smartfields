"""Tests for engine/lint.py (written before the code; spec 7.13, 11.4 test 6).

Test 6: on a hand-made table with one known error per rule, each rule fires exactly once.
"""
import pandas as pd
import pytest

from engine import lint

D = pd.Timestamp


def tables(organic=0):
    parcels = ["P1", "P2", "P3"]
    planting = pd.DataFrame({"parcel_id": parcels, "year": 2024, "crop": ["BARL", "MAIZ", "COWT"],
                             "plant_date": [D("2023-10-05"), D("2024-04-25"), D("2023-10-10")]})
    harvest = pd.DataFrame({"parcel_id": parcels, "year": 2024, "crop": ["BARL", "MAIZ", "COWT"],
                            "harvest_date": [D("2024-07-10"), D("2024-09-20"), D("2024-07-25")]})
    irrigation = pd.DataFrame({"parcel_id": parcels, "year": 2024, "irrigated": [0, 1, 0], "water_mm": [0, 80, 0]})
    fert = pd.DataFrame({
        "fertilisation_id": [1, 2, 3, 4, 5, 6],
        "parcel_id": ["P1", "P1", "P2", "P2", "P3", "P3"], "year": 2024,
        "app_date": [D("2024-03-10"), D("2024-04-15"),                 # P1: identical rows -> R5 (2 rows)
                     D("2024-05-20"), D("2024-06-20"),                 # P2: irrigated, fertigation fine
                     D("2023-12-15"), D("2024-04-02")],                # P3: Dec -> R3; fertigation on non-irrigated -> R4
        "product_type": ["MINERAL"] * 6,
        "n_kg_ha": [60.0, 60.0, 40.0, 50.0, 30.0, 70.0],
        "p2o5_kg_ha": [20.0, 20.0, 10.0, 12.0, 0.0, 15.0],
        "k2o_kg_ha": [10.0] * 6,
        "method": ["BROADCAST", "BROADCAST", "FERTIGATION", "FERTIGATION", "BROADCAST", "FERTIGATION"]})
    pp = pd.DataFrame({
        "pp_id": [11, 12, 13], "parcel_id": ["P1", "P2", "P3"], "year": 2024,
        "app_date": [D("2024-05-02"), D("2024-09-30"), D("2024-05-06")],  # P2: spray after harvest -> R1; P3 6 May windy -> R6
        "product_type": ["FUNGICIDE", "HERBICIDE", "FUNGICIDE"], "product_name": ["A", "B", "C"],
        "active_substance": ["x", "y", "z"], "dose_l_or_kg_ha": [1.0, 1.0, 1.0], "crop_stage_bbch": [31, 99, 32]})
    weather = pd.DataFrame({"date": pd.date_range("2023-10-01", "2024-12-31")})
    weather["precip_mm"], weather["tmax_c"], weather["wind_m_s"] = 0.0, 10.0, 2.0
    weather.loc[weather.date == "2024-05-06", "wind_m_s"] = 6.0
    holding = {"holding_id": "F1", "organic": organic}
    return dict(planting=planting, harvest=harvest, irrigation=irrigation, fertilisation=fert,
                plant_protection=pp), weather, holding


def test_each_rule_fires_exactly_once_on_hand_made_table():
    t, wx, h = tables()
    res = lint.lint(t, wx, h, campaign=2024)
    flags = res["flags"]
    counts = flags.groupby("rule").record_id.nunique().to_dict()
    assert counts == {"R1": 1, "R3": 1, "R4": 1, "R5": 2, "R6": 1}     # R5 flags both rows of the one parcel-year
    issues = {c["rule"] for c in res["cards"] if c["severity"] == "issue"}
    assert issues == {"R1", "R3", "R4", "R5"}
    assert "R2" not in counts                                             # not organic


def test_rule_details_point_at_the_right_records():
    t, wx, h = tables()
    f = lint.lint(t, wx, h, campaign=2024)["flags"].set_index("rule")
    assert f.loc["R1", "record_id"] == 12 and f.loc["R3", "record_id"] == 5
    assert f.loc["R4", "record_id"] == 6 and f.loc["R6", "record_id"] == 13


def test_organic_holding_flags_mineral_fertiliser_and_herbicide():
    t, wx, h = tables(organic=1)
    res = lint.lint(t, wx, h, campaign=2024)
    r2 = res["flags"][res["flags"].rule.str.startswith("R2")]
    assert set(r2.record_type) == {"fertilisation", "plant_protection"}
    assert (r2.record_type == "fertilisation").sum() == 6 and (r2.record_type == "plant_protection").sum() == 1


def test_cards_group_flags_into_root_causes_with_fix_and_rows():
    t, wx, h = tables()
    res = lint.lint(t, wx, h, campaign=2024)
    assert res["n_records"] == 9 and res["n_flags"] == 6 and res["n_root_causes"] == 4
    for c in res["cards"]:
        assert c["title"] and c["why"] and c["fix"] and isinstance(c["rows"], pd.DataFrame) and len(c["rows"]) == c["n_rows"]
    assert [c["severity"] for c in res["cards"]][-1] == "check"            # checks after issues


def test_campaign_filter_and_clean_data():
    t, wx, h = tables()
    assert lint.lint(t, wx, h, campaign=2019)["n_records"] == 0
    t["fertilisation"] = t["fertilisation"].iloc[2:4]                     # only clean, irrigated fertigation rows
    t["plant_protection"] = t["plant_protection"].iloc[:1]
    res = lint.lint(t, wx, h, campaign=2024)
    assert res["n_flags"] == 0 and res["cards"] == []


def test_frozen_soil_counts_as_r3():
    t, wx, h = tables()
    wx.loc[wx.date == "2024-03-10", "tmax_c"] = -1.0
    f = lint.lint(t, wx, h, campaign=2024)["flags"]
    assert set(f[f.rule == "R3"].record_id) == {1, 5}


# ---------------------------------------------------------------- real data (spec 10: 2024 campaign)
@pytest.mark.needs_data
def test_real_2024_campaign_numbers():
    res = lint.lint_records("FARM-13525", 2024)
    assert res["n_records"] == 177 and res["n_flags"] == 143 and res["n_root_causes"] == 4
    by = {c["rule"]: c["n_rows"] for c in res["cards"]}
    assert by == {"R5": 85, "R4": 18, "R3": 13, "R1": 12, "R6": 15}


@pytest.mark.needs_data
def test_real_organic_example():
    res = lint.lint_records("FARM-16285", None)
    by = {c["rule"]: c["n_rows"] for c in res["cards"]}
    assert by["R2-fert"] == 1316 and by["R2-herb"] == 229


@pytest.mark.needs_data
def test_real_wet_day_operations_2024():
    w = lint.wet_day_operations("FARM-13525", 2024)
    assert w["n_operations"] == 279 and w["n_assessed"] == 279
    assert 0.10 < w["share_nogo"] < 0.30
    assert set(w["by_operation"].table) == {"planting", "fertilisation", "plant_protection", "harvest"}
    # it is a separate analysis: the root-cause numbers of the demo stay the same
    assert lint.lint_records("FARM-13525", 2024)["n_flags"] == 143
