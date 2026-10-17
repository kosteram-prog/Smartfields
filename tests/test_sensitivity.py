"""B7: one assumption at a time; the base row must reproduce the agreed demo numbers; params are restored."""
import pytest

from engine import params as prm
from engine import sensitivity


def test_override_restores_params():
    go = prm.THRESHOLDS["L2"]["go"].value
    k = prm.BUCKET["transient_k"].value
    with sensitivity._override("thresholds", -0.05):
        assert prm.THRESHOLDS["L2"]["go"].value == pytest.approx(go - 0.05)
    with sensitivity._override("transient_k", 0.2):
        assert prm.BUCKET["transient_k"].value == 0.2
    assert prm.THRESHOLDS["L2"]["go"].value == go and prm.BUCKET["transient_k"].value == k


@pytest.mark.needs_data
def test_base_and_key_variants_match_pre_event_table():
    base = sensitivity.run_variant(None, None)
    # FC at -10 kPa (17 Oct); pre-event (FC -33 kPa): P 0.6, 22 Oct, 3 workable days, stricter: not done by 30 Nov
    assert base["P"] == pytest.approx(0.8) and base["done_2016"] == "17 Oct" and base["contractor"] == 5
    assert base["workable_days_2016"] == 8 and base["demo_13oct"] == "C/N · G/C"
    stricter = sensitivity.run_variant("thresholds", -0.05)
    assert stricter["done_2016"] == "18 Oct" and stricter["demo_13oct"] == "N/N · C/C"
    assert sensitivity.run_variant("caution_weight", 1.0)["P"] == pytest.approx(1.0)
