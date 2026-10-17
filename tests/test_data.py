"""Tests for engine/data.py (written before the code).

Part 1 runs on a tiny fake archive built in tmp_path (no organisers' data needed).
Part 2 (needs_data) checks the real counts from the pre-event test (spec section 6 / 7.1).
"""
import zipfile

import pandas as pd
import pytest

from engine import data

ROOT = "dg-agri-hackathon-datasets/"
DEMO, ORGANIC, OTHER = "FARM-13525", "FARM-16285", "FARM-00001"
EXPECTED_FILES = ["wx", "holding", "parcels", "planting", "harvest", "fertilisation", "plant_protection",
                  "irrigation", "prices", "labour", "regional_soil"]

WX_COLS = ("nuts_version,nuts0_id,nuts2_id,nuts3_id,country_code,date,centroid_latitude,centroid_longitude,"
           "temperature_min_c,temperature_mean_c,temperature_max_c,precipitation_mm,relative_humidity_pct,"
           "vapour_pressure_hpa,vapour_pressure_deficit_hpa,solar_radiation_mj_m2,wind_speed_m_s,"
           "reference_evapotranspiration_mm,water_balance_mm,gdd_base_5_c,gdd_base_10_c,frost_day,heat_day,"
           "dry_day,heavy_rain_day,consecutive_dry_days,weighting_method")


def _wx_row(nuts3, date, precip):
    return f"2024,XX,XX1,{nuts3},XX,{date},50.0,17.0,2.0,5.0,9.0,{precip},80,8,1,3,2.5,1.1,0.1,0,0,0,0,0,0,1,w"


def make_archive(path):
    files = {
        "weather/weather_daily_2015.csv": WX_COLS + "\n" + "\n".join(
            _wx_row(n, d, p) for n in ("PL415", "PL418", "RO317", "DE242")
            for d, p in (("2015-01-01", 0.5), ("2015-01-02", 7.25))),
        "weather/weather_daily_2016.csv": WX_COLS + "\n" + "\n".join(
            _wx_row(n, "2016-10-13", 0.1) for n in ("PL415", "DE242")),
        "synthetic/synthetic_holding.csv":
            "holding_id,nuts3,farm_type_tf8,econ_size_class,uaa_ha,organic,altitude_zone,anc_flag,natura2000_flag,statistical_weight\n"
            f"{DEMO},PL415,1,3,307.9,0,1,0,0,10\n{ORGANIC},PL415,1,3,200.0,1,1,0,0,10\n{OTHER},ES418,5,2,19.6,0,1,0,1,10\n",
        "synthetic/synthetic_parcel.csv":
            "parcel_id,holding_id,area_ha,crop_current,crop_previous,crop_use,tenure,x_local_m,y_local_m,shape_wkt\n"
            f"PARCEL-0149869,{DEMO},7.61,BARL,MAIZ,FOOD,OWNED,1,2,\"POLYGON((0 0, 1 0, 1 1, 0 0))\"\n"
            f"PARCEL-0149906,{DEMO},6.34,BARL,MAIZ,FOOD,OWNED,3,4,\"POLYGON((0 0, 1 0, 1 1, 0 0))\"\n"
            f"PARCEL-0200001,{ORGANIC},9.0,COWT,MAIZ,FOOD,OWNED,5,6,\"POLYGON((0 0, 1 0, 1 1, 0 0))\"\n"
            f"PARCEL-0000001,{OTHER},8.24,HAY,MAIZ,FEED,OWNED,7,8,\"POLYGON((0 0, 1 0, 1 1, 0 0))\"\n",
        "synthetic/synthetic_soil.csv":
            "parcel_id,ph_h2o,lime_requirement_t_ha,soc_g_kg,organic_matter_pct,nitrogen_g_kg,phosphorus_mg_kg,potassium_mg_kg,"
            "sulfur_mg_kg,calcium_mg_kg,magnesium_mg_kg,zinc_mg_kg,boron_mg_kg,sand_pct,silt_pct,clay_pct,cec_cmol_kg,bulk_density_kg_dm3\n"
            "PARCEL-0149869,6.6,0,11.2,2.5,2.6,79,247,10,2648,105,4,0.6,15.0,30.2,54.8,13,1.5\n"
            "PARCEL-0149906,6.8,0,9.0,1.5,2.0,70,200,10,2000,100,4,0.6,77.6,14.4,8.0,9,1.4\n"
            "PARCEL-0200001,6.5,0,10.0,2.0,2.0,60,200,10,2000,100,4,0.6,40.0,35.0,25.0,12,1.4\n"
            "PARCEL-0000001,6.6,0,11.2,1.93,2.68,79.7,247.4,10.4,2648,105.5,4.18,0.65,58.5,31.4,10.1,13.1,1.5\n",
        "synthetic/synthetic_planting_2017.csv":
            "planting_id,parcel_id,year,plant_date,crop,variety,seed_origin,seed_rate_kg_ha\n"
            "1,PARCEL-0149869,2017,2016-10-05,BARL,BARL-V1,CERTIFIED,160\n2,PARCEL-0000001,2017,2017-03-25,HAY,HAY-V14,NONE,0\n",
        "synthetic/synthetic_harvest_2017.csv":
            "harvest_id,parcel_id,year,harvest_date,crop,yield_t_ha,moisture_pct,protein_pct,air_temp_c,air_humidity_pct\n"
            "1,PARCEL-0149869,2017,2017-07-20,BARL,5.4,14,\\N,25,50\n2,PARCEL-0000001,2017,2017-06-04,HAY,3.85,16.6,\\N,29.9,46\n",
        "synthetic/synthetic_fertilisation_2017.csv":
            "fertilisation_id,parcel_id,year,app_date,product_type,n_kg_ha,p2o5_kg_ha,k2o_kg_ha,method\n"
            "1,PARCEL-0149869,2017,2017-03-05,MINERAL,60,\\N,10,BROADCAST\n2,PARCEL-0000001,2017,2017-05-24,ORGANIC,39.9,14.4,15.3,VARIABLE_RATE\n",
        "synthetic/synthetic_plant_protection_2017.csv":
            "pp_id,parcel_id,year,app_date,product_type,product_name,active_substance,dose_l_or_kg_ha,crop_stage_bbch\n"
            "1,PARCEL-0149906,2017,2017-04-28,HERBICIDE,Terravance 729,AS-HER-03,2.66,\\N\n2,PARCEL-0000001,2017,2017-09-10,FUNGICIDE,X,AS-FUN-22,0.39,12\n",
        "synthetic/synthetic_irrigation_2017.csv":
            "irrigation_id,parcel_id,year,irrigated,water_mm\n1,PARCEL-0149869,2017,0,0.0\n2,PARCEL-0000001,2017,1,50.0\n",
        "synthetic/synthetic_market_price.csv": "price_id,product,year,month,price_eur_t\n1,COWT,2017,7,247.0\n2,BARL,2017,7,225.0\n",
        "soil/soil_soil_topsoil_ready.csv":
            "nuts_version,nuts0_id,nuts2_id,nuts3_id,country_code,topsoil_ph_h2o,topsoil_organic_carbon_g_kg,"
            "topsoil_nitrogen_g_kg,topsoil_bulk_density_kg_dm3,topsoil_clay_g_kg,topsoil_sand_g_kg,topsoil_silt_g_kg\n"
            "2024,PL,PL41,PL418,PL,6.3,23.7,1.5,1.4,94.3,726.4,179.3\n2024,DE,DE24,DE242,DE,6.0,20.0,1.5,1.4,200,400,400\n",
        "combined/combined_labour_summary.csv":
            "holding_id,static_labour_record_count,static_labour_awu,static_labour_annual_hours\n"
            f"{DEMO},2,4.89,8800\n{OTHER},2,1.19,2144\n",
    }
    with zipfile.ZipFile(path, "w") as z:
        for name, text in files.items():
            z.writestr(ROOT + name, text)
    return path


@pytest.fixture()
def extracted(tmp_path, monkeypatch):
    zip_path = make_archive(tmp_path / "fake.zip")
    out = tmp_path / "extracts"
    summary = data.extract(zip_path, out)
    monkeypatch.setenv("FIELDGO_DATA_DIR", str(out))
    return out, summary


# ------------------------------------------------------------------ part 1: logic on a fake archive
def test_extract_writes_all_parquet_files(extracted):
    out, summary = extracted
    for name in EXPECTED_FILES:
        assert (out / f"{name}.parquet").exists(), name
    assert set(summary) >= set(EXPECTED_FILES)


def test_weather_filtered_to_three_regions_and_typed(extracted):
    out, _ = extracted
    wx = pd.read_parquet(out / "wx.parquet")
    assert set(wx.nuts3_id) == {"PL415", "PL418", "RO317"} | {"PL415"}   # DE242 dropped
    assert "DE242" not in set(wx.nuts3_id)
    assert len(wx) == 3 * 2 + 1                                           # 2015 rows + the one 2016 PL415 row
    assert pd.api.types.is_datetime64_any_dtype(wx["date"])
    assert wx.precipitation_mm.max() == pytest.approx(7.25)


def test_parcels_only_demo_holdings_with_soil_and_holding_fields(extracted):
    out, _ = extracted
    p = pd.read_parquet(out / "parcels.parquet")
    assert set(p.holding_id) == {DEMO, ORGANIC}
    assert len(p) == 3
    assert p.parcel_id.map(type).eq(str).all()
    row = p.set_index("parcel_id").loc["PARCEL-0149869"]
    assert row.clay_pct == 54.8 and row.sand_pct == 15.0 and row.organic_matter_pct == 2.5
    assert row.nuts3 == "PL415"
    assert p.set_index("parcel_id").loc["PARCEL-0200001", "organic"] == 1


def test_operations_filtered_by_demo_parcels_and_null_marker(extracted):
    out, _ = extracted
    fert = pd.read_parquet(out / "fertilisation.parquet")
    assert set(fert.parcel_id) == {"PARCEL-0149869"}            # the other farm's parcel is dropped
    assert fert.p2o5_kg_ha.isna().all()                          # \N -> missing, never 0
    pp = pd.read_parquet(out / "plant_protection.parquet")
    assert pp.crop_stage_bbch.isna().all()
    assert set(pd.read_parquet(out / "harvest.parquet").parcel_id) == {"PARCEL-0149869"}


def test_prices_all_rows_and_labour_demo_only(extracted):
    out, _ = extracted
    assert len(pd.read_parquet(out / "prices.parquet")) == 2
    assert set(pd.read_parquet(out / "labour.parquet").holding_id) == {DEMO}


def test_load_weather_contract(extracted):
    wx = data.load_weather("PL415")
    assert list(wx.columns[:7]) == ["date", "precip_mm", "et0_mm", "tmin_c", "tmean_c", "tmax_c", "wind_m_s"]
    assert wx.date.is_monotonic_increasing and wx.date.is_unique
    assert (wx.origin == "real").all()
    with pytest.raises(ValueError):
        data.load_weather("XX999")


def test_load_farm_contract_and_hydraulics(extracted):
    farm = data.load_farm(DEMO)
    for col in ["parcel_id", "crop", "area_ha", "clay_pct", "sand_pct", "om_pct", "fc_mm", "wp_mm", "priority", "origin"]:
        assert col in farm.columns, col
    assert len(farm) == 2 and (farm.origin == "synthetic").all()
    assert (farm.fc_mm > farm.wp_mm).all() and (farm.wp_mm > 0).all()   # Saxton-Rawls, 0-30 cm
    assert farm.priority.isna().all()                                    # not available until engine.season
    assert farm.set_index("parcel_id").loc["PARCEL-0149906", "sand_pct"] == 77.6
    with pytest.raises(ValueError):
        data.load_farm("FARM-99999")


def test_load_operations_filters_by_holding(extracted):
    assert set(data.load_operations("planting", DEMO).parcel_id) == {"PARCEL-0149869"}
    assert data.load_operations("irrigation", ORGANIC).empty
    with pytest.raises(ValueError):
        data.load_operations("tillage", DEMO)


def test_loaders_give_a_clear_error_without_data_dir(monkeypatch):
    monkeypatch.delenv("FIELDGO_DATA_DIR", raising=False)
    with pytest.raises(RuntimeError, match="FIELDGO_DATA_DIR"):
        data.load_farm(DEMO)


def test_loaders_return_copies(extracted):
    a = data.load_farm(DEMO)
    a.loc[:, "area_ha"] = -1
    assert (data.load_farm(DEMO).area_ha > 0).all()


# ------------------------------------------------------------------ part 2: real extract (spec sections 6 and 7.1)
@pytest.mark.needs_data
def test_real_demo_farm_counts():
    farm = data.load_farm(DEMO)
    assert len(farm) == 51
    assert farm.area_ha.sum() == pytest.approx(307.9, abs=0.1)
    barl, cowt = farm[farm.crop == "BARL"], farm[farm.crop == "COWT"]
    assert len(barl) == 12 and barl.area_ha.sum() == pytest.approx(78.2, abs=0.1)
    assert len(cowt) == 9 and cowt.area_ha.sum() == pytest.approx(55.6, abs=0.1)


@pytest.mark.needs_data
@pytest.mark.parametrize("nuts3", ["PL415", "PL418", "RO317"])
def test_real_weather_has_every_day_2015_2024(nuts3):
    wx = data.load_weather(nuts3)
    assert len(wx) == 3653                       # 10 years incl. 3 leap days (the prompt says 3,652: off by one)
    assert wx.date.min() == pd.Timestamp("2015-01-01") and wx.date.max() == pd.Timestamp("2024-12-31")
    assert wx.precip_mm.notna().all()


@pytest.mark.needs_data
def test_real_organic_example_farm_present():
    farm = data.load_farm(ORGANIC)
    assert len(farm) > 0 and (farm.organic == 1).all()


def test_regional_soil_as_parcel_texture(extracted):
    r = data.load_regional_soil("PL418")
    assert r["clay_pct"] == pytest.approx(9.4) and r["sand_pct"] == pytest.approx(72.6)
    assert r["om_pct"] == pytest.approx(23.7 * 1.724 / 10, abs=0.01) and r["origin"] == "modelled"
    with pytest.raises(ValueError):
        data.load_regional_soil("DE242")                    # filtered out at extraction


@pytest.mark.needs_data
def test_parcel_shapes_are_closed_polygons_for_every_parcel():
    from engine import data
    s = data.load_parcel_shapes("FARM-13525")
    farm = data.load_farm("FARM-13525")
    assert set(s.parcel_id) == set(farm.parcel_id)
    for r in s.itertuples():
        assert len(r.xs) == len(r.ys) >= 4 and r.xs[0] == r.xs[-1] and r.ys[0] == r.ys[-1]
