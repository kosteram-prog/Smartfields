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
    assert base["P"] == pytest.approx(0.6) and base["done_2016"] == "22 Oct" and base["contractor"] == 5
    assert base["workable_days_2016"] == 3 and base["demo_13oct"] == "C/N · G/C"
    stricter = sensitivity.run_variant("thresholds", -0.05)
    assert stricter["done_2016"] == "not done by 30 Nov" and stricter["demo_13oct"] == "N/N · C/C"
    assert sensitivity.run_variant("caution_weight", 1.0)["P"] == pytest.approx(1.0)
