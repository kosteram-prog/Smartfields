"""B5: model vs Sentinel-1 radar on the real Gasawy field, October 2016."""
import pytest

from engine import validate


@pytest.mark.needs_data
def test_radar_and_model_both_see_the_rain():
    r = validate.radar_vs_model()
    assert r["field"]["sand_pct"] > 70 and r["n_dates"] == 8
    m = r["radar"].set_index("date")
    assert m.loc["2016-09-29", "RWC_eff"] < 0.2 and m.loc["2016-10-05", "RWC_eff"] >= 1.0      # dry -> wet
    assert r["vv_change_db"] == pytest.approx(5.2, abs=0.01)
    assert r["spearman_all"] > 0.7
