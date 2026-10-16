"""The stubs must keep the demo numbers of the pre-event test (spec section 6) and the engine contract."""
import inspect

import pytest

from engine import stubs

CONTRACT = ["load_farm", "load_weather", "soil_water", "axle_load_class", "classify_day", "status_table",
            "season", "season_cost", "contractor_value", "wait_cost", "today", "safer_plan", "make_record",
            "lint_records"]


@pytest.mark.parametrize("name", CONTRACT)
def test_every_contract_function_has_a_stub(name):
    assert callable(getattr(stubs, name))


def test_season_demo_numbers():
    assert stubs.season({})["P_by_deadline"]["value"] == pytest.approx(0.6)
    assert stubs.season({"contractor_ha_day": 5})["P_by_deadline"]["value"] == pytest.approx(0.9)


def test_today_demo_cases_13_oct_2016():
    d = "2016-10-13"
    assert stubs.today("PARCEL-0149869", d, "M3", 100)["status"] == "NO-GO"
    assert stubs.today("PARCEL-0149869", d, "M2", 100)["status"] == "CAUTION"
    assert stubs.today("PARCEL-0149906", d, "M2", 100)["status"] == "GO"
    assert stubs.wait_cost(d)["eur"] == 1700.0


def test_missing_value_is_not_available_never_zero():
    assert stubs.wait_cost("2020-01-01")["eur"] == "not available"
    assert stubs.contractor_value(contractor_price=None)["net_benefit_worst"] == "not available"


def test_lint_cards_2024():
    res = stubs.lint_records("FARM-13525", 2024)
    assert [c["n_rows"] for c in res["cards"]] == [85, 18, 13, 12] and res["n_flags"] == 143


def test_cost_demo_numbers():
    c = stubs.season_cost()
    assert c["median"]["weather_default"] == 2600 and c["worst_year"]["weather_default"] == 10700


def test_outputs_carry_origin():
    assert stubs.load_farm()["origin"].notna().all()
    assert "origin" in stubs.today("PARCEL-0149906", "2016-10-13")
