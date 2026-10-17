"""Tests for engine/compaction.py (written before the code; 17 Oct, tyre-based compaction check).

Simplified Terranimo-style chain: wheel load + tyre inflation pressure -> mean ground pressure and footprint ->
vertical stress at depth (Soehne/Froehlich, concentration factor from soil wetness) -> compared with soil strength
(precompression stress from clay and matric potential) -> risk class per depth (SCI = log10 stress/strength).
No organisers' data needed.
"""
import math

import pandas as pd
import pytest

from engine import compaction as cp
from engine import params as prm

C = prm.COMPACTION


# ---------------------------------------------------------------- contact (tyre-soil interface)
def test_contact_mean_ground_pressure_and_area():
    c = cp.contact(4.0, 1.8)
    mgp = 1.8 * 100 + C["carcass_kpa"].value
    assert c["mgp_kpa"] == pytest.approx(mgp)
    assert c["area_m2"] == pytest.approx(4.0 * 9.81 / mgp)
    assert c["radius_m"] == pytest.approx(math.sqrt(c["area_m2"] / math.pi))


def test_contact_lower_pressure_gives_larger_footprint():
    assert cp.contact(4.0, 1.0)["area_m2"] > cp.contact(4.0, 2.0)["area_m2"]


@pytest.mark.parametrize("load, bar", [(0, 1.5), (4, 0), (-1, 1.0), (None, 1.0), (4, None)])
def test_contact_rejects_missing_or_non_physical_inputs(load, bar):
    assert cp.contact(load, bar) is None


# ---------------------------------------------------------------- stress propagation
def test_froehlich_with_nu_3_is_boussinesq_uniform_circle():
    p, a, z = 150.0, 0.25, 0.4
    bouss = p * (1 - z ** 3 / (z ** 2 + a ** 2) ** 1.5)
    assert cp.vertical_stress(p, a, z, 3.0) == pytest.approx(bouss)


def test_stress_decreases_with_depth_and_concentrates_with_higher_nu():
    p, a = 150.0, 0.25
    s = [cp.vertical_stress(p, a, z, 5.0) for z in (0.0, 0.1, 0.3, 0.5, 0.8)]
    assert s[0] == pytest.approx(p) and all(x > y for x, y in zip(s, s[1:]))
    assert cp.vertical_stress(p, a, 0.5, 6.0) > cp.vertical_stress(p, a, 0.5, 4.0)


def test_depth_of_stress_round_trip_and_unreachable_target():
    p, a, nu = 150.0, 0.25, 5.0
    z = cp.depth_of_stress(p, a, nu, 50.0)
    assert cp.vertical_stress(p, a, z, nu) == pytest.approx(50.0, rel=1e-6)
    assert cp.depth_of_stress(40.0, a, nu, 50.0) == 0.0                 # surface pressure below the target


def test_rules_of_thumb_load_drives_subsoil_pressure_drives_topsoil():
    # Schjoenning et al. 2012: the 50 kPa contour goes ~8 cm deeper per extra tonne of wheel load
    nu = 5.0
    d3 = cp.depth_of_stress(**_mgp_a(3.0, 1.5), nu=nu, target_kpa=50.0)
    d4 = cp.depth_of_stress(**_mgp_a(4.0, 1.5), nu=nu, target_kpa=50.0)
    assert 0.04 <= d4 - d3 <= 0.15
    # lowering the inflation pressure cuts topsoil stress relatively more than subsoil stress
    hi, lo = _mgp_a(4.0, 2.0), _mgp_a(4.0, 1.0)
    top = cp.vertical_stress(lo["p"], lo["a"], 0.1, nu) / cp.vertical_stress(hi["p"], hi["a"], 0.1, nu)
    sub = cp.vertical_stress(lo["p"], lo["a"], 0.5, nu) / cp.vertical_stress(hi["p"], hi["a"], 0.5, nu)
    assert top < sub < 1.0


def _mgp_a(load_t, bar):
    c = cp.contact(load_t, bar)
    return {"p": c["mgp_kpa"], "a": c["radius_m"]}


# ---------------------------------------------------------------- soil wetness -> pF, concentration factor
def test_concentration_factor_follows_terranimo_anchors():
    assert cp.concentration_factor(1.7) == pytest.approx(6.0)
    assert cp.concentration_factor(2.0) == pytest.approx(5.0)
    assert cp.concentration_factor(2.7) == pytest.approx(4.0)
    assert cp.concentration_factor(4.2) == pytest.approx(3.0)
    assert cp.concentration_factor(1.0) == pytest.approx(6.0)          # clamped at the wet end
    assert cp.concentration_factor(2.35) == pytest.approx(4.5)


def test_pf_from_rwc_full_bucket_is_field_capacity_and_monotonic():
    soil = dict(sand_pct=40.0, clay_pct=20.0, om_pct=2.0)
    fc_pf = math.log10(10 * prm.SAXTON_RAWLS["fc_kpa"].value)                    # -10 kPa = -100 hPa = pF 2.0
    assert fc_pf == pytest.approx(2.0)
    assert cp.pf_from_rwc(1.0, **soil) == pytest.approx(fc_pf)
    pfs = [cp.pf_from_rwc(r, **soil) for r in (1.1, 1.0, 0.8, 0.5, 0.2)]
    assert all(x < y for x, y in zip(pfs, pfs[1:]))
    assert C["pf_min"].value <= min(pfs) and max(pfs) <= C["pf_max"].value
    assert cp.pf_from_rwc(float("nan"), **soil) is None


# ---------------------------------------------------------------- soil strength (precompression stress)
def test_strength_at_pf2_does_not_depend_on_clay():
    assert cp.strength(10.0, 2.0, "topsoil") == pytest.approx(cp.strength(20.0, 2.0, "topsoil"))
    assert cp.strength(10.0, 2.0, "topsoil") == pytest.approx(C["pc_ref_kpa"].value["topsoil"])
    assert cp.strength(10.0, 2.0, "subsoil") == pytest.approx(C["pc_ref_kpa"].value["subsoil"])


@pytest.mark.parametrize("clay, pf, kpa", [(10, 4.2, 300), (20, 3.1, 300), (10, 0.2, 20), (20, 1.1, 20)])
def test_strength_reproduces_terranimo_note_anchor_points(clay, pf, kpa):
    assert cp.strength(clay, pf, "topsoil") == pytest.approx(kpa, rel=0.15)


def test_strength_trends_wetter_is_weaker_and_clay_amplifies():
    assert cp.strength(20, 1.8, "topsoil") < cp.strength(20, 2.5, "topsoil")
    assert cp.strength(20, 1.5, "topsoil") < cp.strength(10, 1.5, "topsoil")     # wet: heavier soil is weaker
    assert cp.strength(20, 2.5, "topsoil") > cp.strength(10, 2.5, "topsoil")     # dry: heavier soil is stronger


def test_strength_beyond_calibrated_clay_is_capped():
    hi = C["clay_calibrated_pct"].value[1]
    assert cp.strength(55.0, 1.8, "subsoil") == pytest.approx(cp.strength(hi, 1.8, "subsoil"))


# ---------------------------------------------------------------- classes
@pytest.mark.parametrize("sci, cls", [(-0.3, "green"), (0.0, "green"), (0.1, "yellow"), (0.18, "yellow"),
                                      (0.2, "red")])
def test_classify_sci(sci, cls):
    assert cp.classify(sci) == cls


# ---------------------------------------------------------------- full check
SOIL = dict(clay_pct=20.0, sand_pct=40.0, om_pct=2.0)


def test_check_contract():
    r = cp.check(2.5, 1.2, rwc_eff=1.0, tmax_c=10.0, **SOIL)
    assert r["assessed"] is True
    for k in ["mgp_kpa", "area_m2", "pf", "nu", "profile", "topsoil", "subsoil", "overall", "stress_50cm_kpa",
              "depth_50kpa_m", "rule_50kpa_50cm", "cost_row", "notes", "origin", "label", "sources"]:
        assert k in r, k
    prof = r["profile"]
    assert isinstance(prof, pd.DataFrame)
    assert list(prof.columns) == ["depth_m", "layer", "stress_kpa", "strength_kpa", "sci", "class"]
    assert set(prof.layer) == {"topsoil", "subsoil"}
    assert r["overall"] == max((r["topsoil"], r["subsoil"]), key=cp.CLASS_RANK.get)
    # the persistent damage (subsoil) picks the cost row; tilled topsoil is usually above its strength (Terranimo)
    assert r["cost_row"] == {"green": "GO", "yellow": "CAUTION", "red": "NO-GO"}[r["subsoil"]]
    assert r["rule_50kpa_50cm"] in ("met", "exceeded")


def test_wetter_soil_never_gives_a_better_class():
    ranks = [cp.CLASS_RANK[cp.check(3.0, 1.6, rwc_eff=w, tmax_c=10.0, **SOIL)["overall"]] for w in (0.6, 0.9, 1.1)]
    assert ranks == sorted(ranks)


def test_heavy_combine_on_wet_soil_is_red_light_tractor_on_dry_soil_is_not():
    assert cp.check(6.5, 2.0, rwc_eff=1.05, tmax_c=10.0, **SOIL)["subsoil"] == "red"
    light = cp.check(1.5, 0.8, rwc_eff=0.6, tmax_c=10.0, **SOIL)
    assert light["subsoil"] == "green" and light["rule_50kpa_50cm"] == "met"


def test_frozen_or_missing_inputs_are_not_assessed():
    assert cp.check(3.0, 1.5, rwc_eff=1.0, tmax_c=-1.0, **SOIL)["assessed"] is False
    r = cp.check(3.0, None, rwc_eff=1.0, tmax_c=10.0, **SOIL)
    assert r["assessed"] is False and r["cost_row"] == "not available"
    assert cp.check(3.0, 1.5, rwc_eff=1.0, tmax_c=10.0, clay_pct=20.0, sand_pct=40.0, om_pct=None)["assessed"] is False


def test_heavy_clay_is_flagged_as_outside_calibration():
    r = cp.check(3.0, 1.5, rwc_eff=1.0, tmax_c=10.0, clay_pct=54.8, sand_pct=23.1, om_pct=3.9)
    assert any("calibrat" in n for n in r["notes"])


# ---------------------------------------------------------------- what would help (levers)
def test_max_wheel_load_keeps_subsoil_green():
    m = cp.max_wheel_load_t(1.2, rwc_eff=1.0, **SOIL)
    assert m > 0
    assert cp.check(m, 1.2, rwc_eff=1.0, tmax_c=10.0, **SOIL)["subsoil"] == "green"
    assert cp.check(m + 0.2, 1.2, rwc_eff=1.0, tmax_c=10.0, **SOIL)["subsoil"] != "green"
    assert cp.max_wheel_load_t(1.2, rwc_eff=0.6, **SOIL) > m                      # drier soil carries more


def test_levers_never_go_below_minimum_field_pressure_and_never_worse():
    base = cp.check(4.0, 2.4, rwc_eff=1.0, tmax_c=10.0, **SOIL)
    lev = cp.levers(4.0, 2.4, rwc_eff=1.0, tmax_c=10.0, **SOIL)
    names = [x["lever"] for x in lev]
    assert "lower tyre pressure" in names and "lighter wheel load" in names
    p = next(x for x in lev if x["lever"] == "lower tyre pressure")
    assert p["inflation_bar"] >= C["min_field_bar"].value
    assert cp.CLASS_RANK[p["overall"]] <= cp.CLASS_RANK[base["overall"]]
    assert cp.CLASS_RANK[p["subsoil"]] <= cp.CLASS_RANK[base["subsoil"]]
    assert "tyre" in p["note"].lower()                                               # check the tyre's load table


# ---------------------------------------------------------------- cost row (6.8.3 table, physics picks the row)
def test_entry_cost_tyre_uses_the_physical_class_for_the_row():
    from engine import cost
    kw = dict(params={"yield_t_ha": {"BARL": 5.0}, "price_eur_t": {"BARL": 200.0}})
    red = {"assessed": True, "subsoil": "red", "overall": "red", "cost_row": "NO-GO"}
    green = {"assessed": True, "subsoil": "green", "overall": "yellow", "cost_row": "GO"}
    assert cost.entry_cost_tyre(red, "L5", "BARL", 10.0, **kw)["eur"] == cost.entry_cost("NO-GO", "L5", "BARL", 10.0, **kw)["eur"]
    assert cost.entry_cost_tyre(green, "L5", "BARL", 10.0, **kw)["eur"] == 0
    assert cost.entry_cost_tyre(red, "L5", "BARL", 10.0, **kw)["method"] == "tyre"
    assert cost.entry_cost_tyre({"assessed": False}, "L5", "BARL", 10.0, **kw)["eur"] == "not available"


# ---------------------------------------------------------------- Today integration (status unchanged)
def test_today_carries_the_tyre_check_without_changing_the_status():
    from tests.test_today import inputs
    from engine import today as td
    parcel = pd.Series({"parcel_id": "P1", "crop": "BARL", "area_ha": 7.6, "clay_pct": 20.0, "sand_pct": 40.0,
                        "om_pct": 2.0})
    sw, wx = inputs(rwc=(1.0, 1.0, 1.0, 1.0))
    a = td.assess(sw, wx, parcel, "2016-10-13", "M3", 100, 1, "sowing")
    b = td.assess(sw, wx, parcel, "2016-10-13", "M3", 100, 1, "sowing", tyre={"inflation_bar": 1.6})
    assert a["status"] == b["status"] and "compaction" not in a
    comp = b["compaction"]
    assert comp["assessed"] and comp["wheel_load_t"] == pytest.approx(b["axle_load_t"] / C["wheels_per_axle"].value)
    assert comp["inflation_bar"] == 1.6
