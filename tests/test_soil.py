"""Tests for engine/soil.py (written before the code; spec 11.4 tests 1-2 + mass balance + contract).

Cases 1-2 are written from the spec because Mirela's cross-written cases are not there yet.
"""
import time

import numpy as np
import pandas as pd
import pytest

from engine import soil

COLS = ["parcel_id", "date", "W_mm", "RWC", "RWC_eff", "rain_today_mm", "rain_prev24h_mm",
        "rain_prev48h_mm", "tmax_c"]
LOAM = dict(sand_pct=40.0, clay_pct=20.0, om_pct=2.5)


def parcels(*rows):
    df = pd.DataFrame(rows or [dict(parcel_id="P-LOAM", **LOAM)])
    return soil.add_hydraulics(df)


def weather(precip, et0=None, start="2016-01-01"):
    n = len(precip)
    et0 = [1.0] * n if et0 is None else et0
    return pd.DataFrame({"date": pd.date_range(start, periods=n), "precip_mm": [float(p) for p in precip],
                         "et0_mm": [float(e) for e in et0], "tmin_c": 5.0, "tmean_c": 10.0, "tmax_c": 15.0,
                         "wind_m_s": 3.0})


# ---------------------------------------------------------------- test 2: Saxton-Rawls
def test_fc_above_wp_for_all_textures():
    s, c = np.meshgrid(np.arange(5, 91, 5), np.arange(5, 61, 5))
    mask = (s + c) <= 100
    wp, fc = soil.saxton_rawls(s[mask], c[mask], 2.0)
    assert (fc > wp).all()


def test_sand_has_lower_field_capacity_than_clay():
    _, fc_sand = soil.saxton_rawls(90.0, 5.0, 1.0)
    _, fc_clay = soil.saxton_rawls(10.0, 50.0, 3.0)
    assert fc_sand < fc_clay


def test_saxton_rawls_reference_values():
    """Hand-computed from the 2006 equations (spec 6.3)."""
    wp, fc = soil.saxton_rawls(15.0, 54.8, 2.5)      # heavy clay parcel PARCEL-0149869
    assert wp == pytest.approx(0.3207, abs=0.002) and fc == pytest.approx(0.4373, abs=0.002)
    wp, fc = soil.saxton_rawls(77.6, 8.0, 1.5)       # sandy parcel PARCEL-0149906
    assert wp == pytest.approx(0.0593, abs=0.002) and fc == pytest.approx(0.1267, abs=0.002)


def test_add_hydraulics_mm_for_30_cm_layer():
    p = parcels(dict(parcel_id="A", sand_pct=15.0, clay_pct=54.8, om_pct=2.5))
    assert p.fc_mm.iloc[0] == pytest.approx(0.4373 * 300, abs=0.7)
    assert p.wp_mm.iloc[0] == pytest.approx(0.3207 * 300, abs=0.7)
    assert (p.taw_mm == p.fc_mm - p.wp_mm).all()


def test_missing_texture_gives_not_available_not_zero():
    p = parcels(dict(parcel_id="A", sand_pct=np.nan, clay_pct=20.0, om_pct=2.0))
    assert np.isnan(p.fc_mm.iloc[0]) and np.isnan(p.wp_mm.iloc[0])


# ---------------------------------------------------------------- test 1: bucket
def test_contract_columns_and_origin():
    sw = soil.soil_water(parcels(), weather([0] * 5))
    assert list(sw.columns[:9]) == COLS
    assert (sw.origin == "modelled").all() and "saturated_today" in sw.columns
    assert len(sw) == 5


def test_rain_brings_loam_to_field_capacity_and_above():
    # a few dry-ish days, 20 mm, then dry again
    p = [0, 0, 0, 0, 0, 20, 0, 0, 0]
    sw = soil.soil_water(parcels(), weather(p)).reset_index(drop=True)
    assert sw.RWC_eff.iloc[5] >= 1.0 and sw.RWC_eff.iloc[6] >= 1.0
    assert sw.RWC.max() <= 1.0 + 1e-9                         # bucket alone never exceeds FC


def test_drying_is_monotonic_after_wet_spell():
    p = [25, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    sw = soil.soil_water(parcels(), weather(p, et0=[3.0] * len(p))).reset_index(drop=True)
    dry = sw.RWC_eff.iloc[2:].to_numpy()                      # after the rain's 48 h window has passed
    assert (np.diff(dry) < 0).all()
    assert sw.RWC.iloc[-1] < sw.RWC.iloc[0]


def test_water_stays_between_wp_and_fc_and_saturation_flag():
    p = [0] * 3 + [12, 0, 40, 0] + [0] * 60
    pr = parcels()
    sw = soil.soil_water(pr, weather(p, et0=[4.0] * len(p)))
    assert (sw.W_mm >= pr.wp_mm.iloc[0] - 1e-9).all() and (sw.W_mm <= pr.fc_mm.iloc[0] + 1e-9).all()
    flagged = sw.loc[sw.saturated_today, "rain_today_mm"]
    assert len(flagged) > 0 and (flagged >= 10).all()


def test_rain_windows():
    sw = soil.soil_water(parcels(), weather([1, 2, 3, 4, 5])).reset_index(drop=True)
    assert sw.rain_today_mm.tolist() == [1, 2, 3, 4, 5]
    assert sw.rain_prev24h_mm.tolist() == [0, 1, 2, 3, 4]
    assert sw.rain_prev48h_mm.tolist() == [1, 3, 5, 7, 9]     # last 48 h = today + yesterday


def test_heavier_soil_holds_more_water():
    pr = parcels(dict(parcel_id="SAND", sand_pct=90.0, clay_pct=5.0, om_pct=1.0),
                 dict(parcel_id="CLAY", sand_pct=10.0, clay_pct=50.0, om_pct=3.0))
    sw = soil.soil_water(pr, weather([0] * 40, et0=[3.0] * 40))
    last = sw.groupby("parcel_id").RWC.last()
    assert last["SAND"] < last["CLAY"]                         # the same ET0 empties the sand faster


def test_missing_or_gappy_weather_raises():
    w = weather([0, 1, 2])
    with pytest.raises(ValueError):
        soil.soil_water(parcels(), w.drop(index=1))            # a missing day
    w.loc[1, "precip_mm"] = np.nan
    with pytest.raises(ValueError):
        soil.soil_water(parcels(), w)


def test_parcel_without_hydraulics_gives_not_available():
    p = parcels(dict(parcel_id="A", sand_pct=np.nan, clay_pct=np.nan, om_pct=np.nan),
                dict(parcel_id="B", **LOAM))
    sw = soil.soil_water(p, weather([0, 5, 0]))
    assert sw[sw.parcel_id == "A"][["W_mm", "RWC", "RWC_eff"]].isna().all().all()
    assert sw[sw.parcel_id == "B"].RWC.notna().all()


# ---------------------------------------------------------------- real data (needs the extracts)
@pytest.mark.needs_data
def test_real_runtime_and_oct_2016_values():
    from engine import data
    farm = data.load_farm("FARM-13525")
    wx = data.load_weather("PL415")
    farm = farm[farm.crop.isin(["BARL", "COWT"])]
    t0 = time.time()
    sw = soil.soil_water(farm, wx)
    assert time.time() - t0 < 5 and len(sw) == 21 * 3653
    d = sw[sw.date == "2016-10-13"].set_index("parcel_id")
    for pid in ("PARCEL-0149869", "PARCEL-0149906"):
        assert 0.90 <= d.loc[pid, "RWC_eff"] <= 1.05, (pid, d.loc[pid, "RWC_eff"])
    # 1 Oct 2016: topsoil near wilting point after a dry September (pre-event test: RWC ~ 0.07)
    assert sw[(sw.date == "2016-10-01") & (sw.parcel_id == "PARCEL-0149869")].RWC.iloc[0] < 0.3


@pytest.mark.needs_data
def test_real_october_2016_bands_match_pre_event_table():
    """RWC_eff bands implied by the pre-event status table (L2/L3 thresholds incl. texture adjustment)."""
    from engine import data
    farm = data.load_farm("FARM-13525")
    sw = soil.soil_water(farm[farm.crop.isin(["BARL", "COWT"])], data.load_weather("PL415"))
    def rwc(pid, day):
        return sw[(sw.parcel_id == pid) & (sw.date == f"2016-10-{day}")].RWC_eff.iloc[0]
    clay, sand = "PARCEL-0149869", "PARCEL-0149906"
    assert 0.95 < rwc(clay, 13) <= 1.00 and 0.95 < rwc(sand, 13) <= 1.00      # clay L2 CAUTION / L3 NO-GO, sand L2 GO
    assert 0.85 < rwc(clay, 14) <= 0.95 and rwc(sand, 14) <= 0.95            # 14 Oct: clay CAUTION/CAUTION, sand GO/GO
    assert rwc(clay, 12) > 1.00 and 1.00 < rwc(sand, 12) <= 1.05             # 12 Oct: clay NO-GO, sand CAUTION
