"""All FieldGo parameters (spec tables 6.1-6.8 + agreed defaults). Data only, no logic.

Every value is a Param(value, unit, origin, source). All are prototype defaults
(origin 'assumption') to be reviewed by the Product Leads. Nothing else in the repo may
hard-code a threshold, rate or date: import it from here.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Param:
    value: object
    unit: str = ""
    origin: str = "assumption"
    source: str = ""


def P(value, unit: str = "", source: str = "", origin: str = "assumption") -> Param:
    return Param(value, unit, origin, source)


ORIGINS = {
    "real": "AgERA5 weather",
    "modelled": "our engine, SoilGrids",
    "synthetic": "organisers' farm, parcels, operations, yields, prices",
    "assumption": "parameter tables (editable)",
}

# ---------------------------------------------------------------- general / demo
DEMO = {
    "holding_id": P("FARM-13525", "", "spec 10", "synthetic"),
    "nuts3": P("PL415", "", "spec 10", "synthetic"),
    "replay_date": P("2016-10-13", "date", "spec 10 (chosen after bucket-model test)"),
    "replay_year_min": P(2015, "year", "AgERA5 coverage", "real"),
    "replay_year_max": P(2024, "year", "AgERA5 coverage", "real"),
    "organic_holding_id": P("FARM-16285", "", "spec 7.13 (R2 example)", "synthetic"),
    "key_parcels": P(
        {"PARCEL-0149869": "heaviest soil, clay 54.8%",
         "PARCEL-0149906": "lightest soil, sand 77.6%",
         "PARCEL-0149917": "clay 39.2%"},
        "", "spec 10", "synthetic"),
}

# ---------------------------------------------------------------- 6.1 machines
# empty axle load = empty_share x loaded axle load (load slider scales linearly)
MACHINES = {
    "M1": dict(profile="Light tractor + mounted tool", mass_t=P(5, "t", "spec 6.1"),
               max_axle_t=P(3, "t", "spec 6.1"), load_class="L1",
               rate_ha_h=P(1.0, "ha/h", "spec 6.1"), empty_share=P(0.80, "", "spec 6.1"),
               operations="light cultivation, small drill"),
    "M2": dict(profile="Medium tractor + 3 m drill combination", mass_t=P(9, "t", "spec 6.1"),
               max_axle_t=P(5, "t", "spec 6.1"), load_class="L2",
               rate_ha_h=P(1.5, "ha/h", "spec 6.1"), empty_share=P(0.80, "", "spec 6.1"),
               operations="sowing (autumn/spring)"),
    "M3": dict(profile="Heavy tractor + 4-6 m cultivator/drill", mass_t=P(14, "t", "spec 6.1"),
               max_axle_t=P(8, "t", "spec 6.1"), load_class="L3",
               rate_ha_h=P(2.5, "ha/h", "spec 6.1"), empty_share=P(0.80, "", "spec 6.1"),
               operations="tillage, sowing"),
    "M4": dict(profile="Self-propelled sprayer, full tank", mass_t=P(14, "t", "spec 6.1"),
               max_axle_t=P(7, "t", "spec 6.1"), load_class="L3",
               rate_ha_h=P(8.0, "ha/h", "spec 6.1"), empty_share=P(0.55, "", "spec 6.1"),
               operations="spraying"),
    "M5": dict(profile="Combine harvester, full grain tank", mass_t=P(22, "t", "spec 6.1"),
               max_axle_t=P(13, "t", "spec 6.1"), load_class="L5",
               rate_ha_h=P(2.0, "ha/h", "spec 6.1"), empty_share=P(0.55, "", "spec 6.1"),
               operations="harvest"),
    "M6": dict(profile="Tractor + slurry tanker (~15 m3), full", mass_t=P(28, "t", "spec 6.1"),
               max_axle_t=P(10, "t", "spec 6.1"), load_class="L5",
               rate_ha_h=P(1.2, "ha/h", "spec 6.1"), empty_share=P(0.55, "", "spec 6.1"),
               operations="organic fertiliser"),
}
# Load class by max axle load (t): lower bound inclusive, upper bound exclusive
LOAD_CLASS_BOUNDS = {
    "L1": P((0, 4), "t", "spec 6.1"), "L2": P((4, 6), "t", "spec 6.1"),
    "L3": P((6, 8), "t", "spec 6.1"), "L4": P((8, 10), "t", "spec 6.1"),
    "L5": P((10, 999), "t", "spec 6.1"),
}

# ---------------------------------------------------------------- 6.2 capacity
CAPACITY = {
    "hours_per_day": P(10, "h", "spec 6.2 / agreed defaults"),
    "own_units": P(1, "units", "spec 6.2"),
    "contractor_ha_day": P(20, "ha/day", "spec 6.2 (demo compares +5 / +10 / +15)"),
    "contractor_step_ha_day": P(5, "ha/day", "spec 7.5"),
    "contractor_target_p": P(0.9, "share", "spec 7.5"),
}

# ---------------------------------------------------------------- 6.3 Saxton & Rawls 2006
# theta = sum(coef * term); terms: S, C, OM, S*OM, C*OM, S*C, const. VERIFY against the paper.
SAXTON_RAWLS = {
    "theta1500t": P(dict(S=-0.024, C=0.487, OM=0.006, S_OM=0.005, C_OM=-0.013, S_C=0.068, const=0.031),
                    "m3/m3", "Saxton & Rawls 2006, SSSAJ 70:1569"),
    "theta1500_adj": P(dict(a=0.14, b=-0.02), "", "Saxton & Rawls 2006 (wilting point)"),
    "theta33t": P(dict(S=-0.251, C=0.195, OM=0.011, S_OM=0.006, C_OM=-0.027, S_C=0.452, const=0.299),
                  "m3/m3", "Saxton & Rawls 2006, SSSAJ 70:1569"),
    "theta33_adj": P(dict(a=1.283, b=-0.374, c=-0.015), "", "Saxton & Rawls 2006 (field capacity)"),
}

# ---------------------------------------------------------------- 7.2 soil-water bucket
BUCKET = {
    "layer_depth_mm": P(300, "mm", "agreed defaults (0-30 cm)"),
    "initial_date": P("2015-01-01", "date", "spec 7.2 (spin-up, W = FC)"),
    "beta_taw_fraction": P(0.5, "", "spec 7.2 (beta = clip((W-WP)/(0.5 TAW), 0, 1))"),
    "saturated_flag_rain_mm": P(10, "mm", "spec 7.2"),
    "transient_k": P(0.1, "", "spec 7.2 (RWC_eff = RWC + k * min(1, P48/ref))"),
    "transient_ref_mm": P(20, "mm", "spec 7.2"),
}

# ---------------------------------------------------------------- 6.4 trafficability
# status GO if RWC_eff <= go, CAUTION if <= caution, otherwise NO-GO
THRESHOLDS = {
    "L1": dict(go=P(1.00, "RWC", "spec 6.4"), caution=P(1.10, "RWC", "spec 6.4")),
    "L2": dict(go=P(0.95, "RWC", "spec 6.4"), caution=P(1.05, "RWC", "spec 6.4")),
    "L3": dict(go=P(0.90, "RWC", "spec 6.4"), caution=P(1.00, "RWC", "spec 6.4")),
    "L4": dict(go=P(0.85, "RWC", "spec 6.4"), caution=P(0.95, "RWC", "spec 6.4")),
    "L5": dict(go=P(0.80, "RWC", "spec 6.4"), caution=P(0.90, "RWC", "spec 6.4")),
}
TEXTURE_ADJUSTMENT = {
    "clay_min_pct": P(30, "%", "spec 6.4"), "clay_delta": P(-0.05, "RWC", "spec 6.4"),
    "sand_min_pct": P(70, "%", "spec 6.4"), "sand_delta": P(+0.05, "RWC", "spec 6.4"),
}
RAIN_OVERRIDES = {
    "rain_today_nogo_mm": P(5, "mm", "spec 6.4: >= 5 mm today -> NO-GO"),
    "rain_prev24h_caution_mm": P(10, "mm", "spec 6.4: >= 10 mm in previous 24 h -> at best CAUTION"),
}
FROST = {
    "tmax_c": P(0, "degC", "spec 6.4: Tmax <= 0 -> frozen soil"),
    "traffic_go_classes": P(("L1", "L2", "L3"), "", "spec 6.4: frozen soil carries L1-L3 traffic"),
    "fertilising_nogo": P(True, "", "spec 6.4: any fertilising on frozen soil = NO-GO"),
}
PASSES = {"threshold_delta_per_extra_pass": P(-0.03, "RWC", "spec 7.7 / agreed defaults"),
          "max_passes": P(3, "passes", "spec 7.7")}

# ---------------------------------------------------------------- Season (7.4-7.6)
SEASON = {
    "window_start": P("10-01", "MM-DD", "agreed defaults (after maize)"),
    "deadline": P("10-15", "MM-DD", "agreed defaults"),
    "simulation_end": P("11-30", "MM-DD", "spec 7.5"),
    "caution_weight": P(0.5, "day", "agreed defaults"),
    "caution_weight_options": P((0.0, 0.5, 1.0), "day", "agreed defaults (toggle + sensitivity)"),
    "years": P(tuple(range(2015, 2025)), "year", "AgERA5 2015-2024", "real"),
}
PRIORITY = {   # spec 7.6
    "w_crop": P(3, "", "spec 7.6"), "w_clay": P(2, "", "spec 7.6"), "w_area": P(1, "", "spec 7.6"),
    "crop_sensitivity": P({"RAPE": 3, "BARL": 2, "COWT": 1}, "", "spec 7.6"),
    "clay_class": P([(40, 3), (25, 2), (0, 1)], "%", "spec 7.6 (clay >= x -> score)"),
    "area_min_ha": P(7, "ha", "spec 7.6"),
}

# ---------------------------------------------------------------- 6.6 BBCH (winter cereals)
BBCH = {
    "base_temp_c": P(0, "degC", "spec 6.6"),
    "thermal_time": P({0: 0, 10: 150, 11: 250, 12: 350, 13: 450, 21: 550}, "degC-days",
                      "spec 6.6 (Product Leads to confirm)"),
}

# ---------------------------------------------------------------- 6.5 / 6.7 N rules
CLOSED_PERIOD_DEFAULT = P({"start": "12-01", "end": "01-31"}, "MM-DD",
                          "spec 6.5: conservative default, verify per country")
N_RULES = {
    "heavy_rain": dict(rain_mm=P(20, "mm", "spec 6.7"), days=P(3, "days", "spec 6.7"),
                       n_at_risk_pct=P((20, 30), "% of applied N", "spec 6.7")),
    "no_uptake": dict(rain_mm_lt=P(5, "mm", "spec 6.7"), days=P(10, "days", "spec 6.7"),
                      n_at_risk_pct=P((10, 15), "% of applied N", "spec 6.7")),
}

# ---------------------------------------------------------------- 6.8 cost parameters
COST = {
    "optimum_end": {   # MM-DD, per crop code
        "COWT": P("10-01", "MM-DD", "IOR-PIB wheat methodology (west 15 Sep - 1 Oct); to confirm"),
        "BARL": P("09-20", "MM-DD", "IOR-PIB barley methodology, Korbas & Mrowczynski 2012; to confirm"),
        "RAPE": P(None, "MM-DD", "not available (enter manually)"),
    },
    "grace_days": P(0, "days", "spec 6.8.1 (editable)"),
    "loss_rate_pct_per_day": {
        "low": P(0.5, "% per day", "Jonczyk 1998"),
        "default": P(1.0, "% per day", "IUNG Pulawy trials"),
        "high": P(1.5, "% per day", "spec 6.8.1"),
    },
    "loss_cap_pct": P(40, "%", "spec 6.8.1"),
    "contractor_price_eur_ha": P(68, "EUR/ha", "290 PLN/ha ~ EUR 68 (range 63-73); kb.pl survey Jan 2026"),
    "price_months": P((7, 8), "month", "spec 6.8.2 (harvest price, Jul-Aug)"),
    "headline": P("weather", "", "agreed defaults: weather part is the headline, late-start shown separately"),
}
# 6.8.3 stretch (Add-on 3, not built by default)
WET_TRAFFIC_LOSS = {
    "NO-GO": {"L1": P(0, "%"), "L2": P(0, "%"), "L3": P(5, "%"), "L4": P(10, "%"), "L5": P(15, "%")},
    "CAUTION": {"L1": P(0, "%"), "L2": P(0, "%"), "L3": P(2.5, "%"), "L4": P(5, "%"), "L5": P(7.5, "%")},
    "trafficked_share": P(0.30, "share", "spec 6.8.3, editable"),
}

# ---------------------------------------------------------------- 7.9 confidence
CONFIDENCE = {
    "start": P(100, "points", "spec 7.9"),
    "weather_regional": P(-20, "points", "spec 7.9"),
    "soil_synthetic": P(-15, "points", "spec 7.9"),
    "default_machine": P(-10, "points", "spec 7.9"),
    "replay_not_forecast": P(-5, "points", "spec 7.9 (label only)"),
    "missing_load": P(-5, "points", "spec 7.9"),
    "missing_passes": P(-5, "points", "spec 7.9"),
    "no_farmer_observation": P(-5, "points", "spec 7.9"),
}

# ---------------------------------------------------------------- PROPOSED by Marek's agent (Task 4, 16 Oct 19:30)
# Operation suitability for Today (spec 7.7). NOT yet agreed: Marek + Mirela to OK (shared file rule).
SUITABILITY = {
    "sowing_rain_caution_mm": P(1.0, "mm", "spec 7.7 'no rain today for sowing'; dataset dry day < 1 mm"),
    "spray_rain_caution_mm": P(1.0, "mm", "proposed: rain during spraying (label: avoid wash-off)"),
    "spray_wind_caution_m_s": P(5.0, "m/s", "spec 7.13 R6 check threshold (mean wind >= 5 m/s)"),
}
CONFIDENCE_LEVELS = {   # label for 'Data quality: ...' (spec 7.9 shows 'medium')
    "high_min": P(70, "points", "proposed"),
    "medium_min": P(40, "points", "proposed"),
}
LINT = {   # RecordLint thresholds (spec 7.13); R6 values from the spec table, PROPOSED block (see above)
    "r6_rain_mm": P(10.0, "mm", "spec 7.13 R6: spray on a day with >= 10 mm rain ('check')"),
    "r6_wind_m_s": P(5.0, "m/s", "spec 7.13 R6: mean wind >= 5 m/s ('check')"),
    "r1_scope": P(("plant_protection",), "", "pre-event test: R1 on sprays only (fertiliser before sowing / "
                  "after harvest is normal practice)"),
    "r2_ppp_types": P(("HERBICIDE",), "", "pre-event test: herbicides counted as synthetic PPP on organic farms"),
}

# ---------------------------------------------------------------- FieldGo integrations (Mirela append)
# Do not edit values above this line in shared PRs without Product Lead review.
# Loss calculator and satellite defaults for pages 6-8.
LOSS_CALC = {
    "recare_compaction_pct": P(6.0, "% of entered output",
        "RECARE soil-compaction literature order of magnitude; not measured on demo farm"),
    "delay_pct_per_day": P(1.0, "% of entered output / day",
        "aligned with COST.loss_rate_pct_per_day['default'] (IUNG Pulawy); illustrative"),
    "default_entered_share_pct": P(100, "%", "UI default: whole farm UAA"),
    "demo_output_eur_ha": P(1200, "EUR/ha",
        "assumption for stub demo when organisers' economics are not loaded"),
}

SATELLITE = {
    "nuts3_latlon": P(
        {"PL415": (52.41, 16.93), "DE242": (50.32, 11.92), "FRB06": (47.50, 1.50),
         "ES418": (41.65, -4.72), "NL226": (51.89, 5.43), "ITC4C": (45.46, 9.19),
         "ITF63": (40.68, 14.77), "ITH55": (45.41, 11.88)},
        "lat,lon", "approximate NUTS3 centroids for map centre"),
    "fallback_tiles": P(
        "https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2021_3857/default/GoogleMapsCompatible/{z}/{y}/{x}.jpg",
        "URL template", "public EOX Sentinel-2 cloudless mosaic (no API key)"),
    "env_token_name": P("COPERNICUS_ACCESS_TOKEN", "",
        "optional CDSE token via env; never commit real values"),
}

INTEGRATIONS = {
    "partners": P(
        [
            {"id": "john-deere", "name": "John Deere Operations Center",
             "auth": "OAuth 2.0 (Operations Center API)",
             "flows": ["Machines and fleet status", "Field boundaries",
                       "Field operations / as-applied", "Work orders"]},
            {"id": "claas", "name": "CLAAS TELEMATICS",
             "auth": "OAuth / partner API",
             "flows": ["Machines and telemetry", "Field boundaries",
                       "Harvest and field operations", "Fleet utilisation"]},
            {"id": "fieldview", "name": "Climate FieldView",
             "auth": "OAuth 2.0 (Climate FieldView API)",
             "flows": ["Field boundaries", "Planting and application operations",
                       "Yield layers", "Scouting notes"]},
            {"id": "weather", "name": "Weather stations",
             "auth": "API key / station IoT endpoint",
             "flows": ["Local temperature and rainfall", "Soil moisture (if supported)",
                       "Hourly observations for GO / NO-GO", "Threshold alerts"]},
        ],
        "", "UI connection points only — no live vendor login in this prototype"),
}

# ---------------------------------------------------------------- PROPOSED: EPPO crop codes for records (spec 6.5, 7.11)
EPPO_CODES = P({"COWT": "TRZAW", "BARL": "HORVW", "RAPE": "BRSNW", "MAIZ": "ZEAMX", "SUNF": "HELAN",
                "HAY": "POAPR", "OLIV": "OLVEU"}, "", "EPPO Global Database: verify each code before submission")
