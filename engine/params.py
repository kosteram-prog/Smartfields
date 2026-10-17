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
    "thetaS33t": P(dict(S=0.278, C=0.034, OM=0.022, S_OM=-0.018, C_OM=-0.027, S_C=-0.584, const=0.078),
                   "m3/m3", "Saxton & Rawls 2006 eq. 3 (moisture between saturation and 33 kPa)"),
    "thetaS33_adj": P(dict(a=0.636, b=-0.107), "", "Saxton & Rawls 2006 eq. 3"),
    "thetaS_sand": P(dict(a=-0.097, b=0.043), "", "Saxton & Rawls 2006 eq. 5: theta_S = theta33 + theta_S33 - 0.097 S + 0.043"),
    # Decision 17 Oct (Marek): field capacity at -10 kPa (pF 2.0), the European / Polish convention and Terranimo's.
    # theta at 10 kPa from the S&R power law psi = A theta^-B through 33 and 1500 kPa (S&R eq. 11-13), capped at
    # saturation. The S&R linear segment between saturation and 33 kPa was rejected (unrealistic for sands).
    "fc_kpa": P(10, "kPa", "decision 17 Oct: European FC (pF 2.0); Richards & Weaver 1944 (-10 kPa for sandy soils); "
                "EU-HYDI / euptf report theta at -100 hPa; Saxton & Rawls 2006 power law extended from 33 to 10 kPa"),
}

# ---------------------------------------------------------------- 7.2 soil-water bucket
BUCKET = {
    "layer_depth_mm": P(300, "mm", "agreed defaults (0-30 cm)"),
    "initial_date": P("2015-01-01", "date", "spec 7.2 (spin-up, W = FC)"),
    "beta_taw_fraction": P(0.5, "", "spec 7.2 (beta = clip((W-WP)/(0.5 TAW), 0, 1))"),
    "saturated_flag_rain_mm": P(10, "mm", "spec 7.2"),
    "transient_k": P(0.1, "", "spec 7.2 (RWC_eff = RWC + k * min(1, P48/ref))"),
    "transient_ref_mm": P(20, "mm", "spec 7.2"),
    "evaporation_model": P("beta", "", "spec 7.2 default: ETa = ET0 x beta. Option 'fao56' (proposed 17 Oct): two-stage "
                           "evaporation of FAO-56 ch. 7 in the bare-soil months, see FAO56"),
}
# Option for the bucket (17 Oct, PROPOSED; default stays 'beta'): FAO-56 two-stage soil evaporation, Allen et al. 1998,
# Irrigation and Drainage Paper 56, ch. 7. TEW = 1000 (theta_FC - 0.5 theta_WP) Ze; Kr = 1 while De <= REW, then
# (TEW - De) / (TEW - REW); E = Kr x ke_max x ET0 (Kr from the previous day's De, as in FAO-56 eq. 74-77).
FAO56 = {
    "ze_m": P(0.10, "m", "FAO-56 ch. 7: depth of the evaporating surface layer 0.10-0.15 m"),
    "rew_mm": P([("sand_min", 85, 4.5), ("sand_min", 70, 6.0), ("sand_min", 50, 8.0), ("clay_min", 40, 10.0),
                 ("else", None, 9.0)], "mm", "FAO-56 Table 19 (midpoints): sand 2-7, loamy sand 4-8, sandy loam 6-10, "
                 "loam / silt loam 8-11, clay 8-12; first matching rule wins"),
    "ke_max": P(1.0, "", "FAO-56 gives Kc_max 1.05-1.30 after wetting; kept at 1.0 so stage 1 equals the default model "
                "and only the drying curve changes"),
    "bare_months": P((10, 11, 12, 1, 2, 3), "month", "assumption: Oct-Mar the soil is bare or under young winter "
                     "cereals (FAO-56 Kcb ini 0.15-0.3); Apr-Sep the crop transpires (default beta model)"),
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
    "clay_min_pct": P(30, "%", "spec 6.4; Obour et al. 2017 (Soil Use Manage.): optimum tillage water ~0.9 x plastic "
                      "limit and on clays FC exceeds it, so a clay soil at FC is never GO"),
    "clay_delta": P(-0.05, "RWC", "spec 6.4"),
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
# Nuance 17 Oct (research review, Marek OK): heavy traffic also needs a soil moisture deficit (SMD = FC - W, here
# (1 - RWC_eff) x TAW of the 0-30 cm layer) of at least 10 mm before it is GO; otherwise at best CAUTION.
SMD_RULE = {
    "go_min_smd_mm": P(10, "mm", "Vero et al. 2014, Soil Use Manage. 30:69-77: SMD >= 10 mm safe for heavy slurry "
                       "tankers on grassland, no difference between drainage classes (adapted to our 0-30 cm layer)"),
    "classes": P(("L5",), "", "heavy traffic only (slurry tankers, combines): the machines of the Vero study"),
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
        "BARL": P("09-20", "MM-DD", "IOR-PIB barley methodology (Korbas & Mrowczynski 2012); confirmed by IUNG "
                  "(Leszczynska & Kostiw 2018): west of Poland 16-20 Sep, 20-25 Sep in long warm autumns"),
        "RAPE": P(None, "MM-DD", "not available (enter manually)"),
    },
    "grace_days": P(0, "days", "spec 6.8.1 (editable)"),
    "loss_rate_pct_per_day": {   # fallback for crops without their own rate
        "low": P(0.5, "% per day", "Jonczyk 1998"),
        "default": P(1.0, "% per day", "IUNG Pulawy trials"),
        "high": P(1.5, "% per day", "spec 6.8.1"),
    },
    # decision 17 Oct (Marek): crop-specific rates (low / default / high, % of yield per day after optimum_end)
    "loss_rate_by_crop": {
        "BARL": P({"low": 0.3, "default": 0.43, "high": 0.6}, "% per day",
                  "winter barley: Green, Furmston & Ivins 1985 (J. Agric. Sci.) 0.43 %/day; LLFG Bernburg 2000-02 "
                  "(Boese 2006) ~2.5 dt/ha per week ~0.38 %/day; range 0.3-0.6"),
        "COWT": P({"low": 0.5, "default": 1.0, "high": 1.5}, "% per day",
                  "winter wheat: IUNG Pulawy trials 1.0; Jonczyk 1998 0.5; Herse & Nelken (central PL) ~0.8"),
    },
    "loss_cap_pct": P(40, "%", "spec 6.8.1"),
    "contractor_price_eur_ha": P(68, "EUR/ha", "290 PLN/ha ~ EUR 68 (range 63-73); kb.pl survey Jan 2026"),
    "price_months": P((7, 8), "month", "spec 6.8.2 (harvest price, Jul-Aug)"),
    "headline": P("weather", "", "agreed defaults: weather part is the headline, late-start shown separately"),
}
# 6.8.3 stretch (Add-on 3, not built by default)
_WTL = "spec 6.8.3: L5 anchor Hakansson multi-site (10-12 t axle ~15% year-1 loss); L3/L4 and CAUTION x0.5 interpolated, illustrative"
WET_TRAFFIC_LOSS = {
    "NO-GO": {"L1": P(0, "%", _WTL), "L2": P(0, "%", _WTL), "L3": P(5, "%", _WTL), "L4": P(10, "%", _WTL),
              "L5": P(15, "%", _WTL)},
    "CAUTION": {"L1": P(0, "%", _WTL), "L2": P(0, "%", _WTL), "L3": P(2.5, "%", _WTL), "L4": P(5, "%", _WTL),
                "L5": P(7.5, "%", _WTL)},
    "trafficked_share": P(0.30, "share", "spec 6.8.3, editable"),
    # decision 17 Oct (Marek): the long-term subsoil part, shown separately from year 1 (undiscounted)
    "persistent": {
        "pct_per_year": P(6, "% of yield per year", "RECARE policy brief (Schjønning, Lamandé, Thorsøe, Frelih-Larsen "
                          "2018): high wheel loads on wet soil -> long-term yield penalty 6-12%; EU estimate ~6%/yr"),
        "years": P(10, "years", "assumption: subsoil compaction persists for decades (RECARE 2018); Håkansson & Reeder "
                   "1994: losses in the subsoil for more than 10 years"),
        "class_factor": P({"L4": 0.5, "L5": 1.0}, "", "table mode: high wheel loads only (Håkansson anchor 10-12 t axle "
                          "= L5; L4 interpolated); L1-L3 not counted"),
        "status_factor": P({"NO-GO": 1.0, "CAUTION": 0.5}, "", "as the CAUTION factor of the 6.8.3 table"),
        "tyre_subsoil_factor": P({"red": 1.0, "yellow": 0.5, "green": 0.0}, "",
                                 "tyre mode: the subsoil class of the compaction check (any load class)"),
    },
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

# ---------------------------------------------------------------- B: validation, wet-day operations, sensitivity (17 Oct)
REAL_FIELD = {
    "name": P("Gasawy 28 (302407_5.0805.28)", "", "GUGiK ULDK; farmer consent confirmed by Marek (14 Oct)", "real"),
    "area_ha": P(80.7, "ha", "GUGiK ULDK", "real"),
    "nuts3": P("PL418", "", "AgERA5 region of the field (rain practically identical to PL415 in Oct 2016)", "real"),
}
# Field-mean Sentinel-1 VV backscatter (gamma0, dB), Oct 2016; pre-event test 14 Oct (Lamia), CDSE Process API.
S1_GASAWY_VV = P([
    ("2016-09-29", "asc A", -12.6), ("2016-09-30", "asc B", -11.8), ("2016-10-05", "asc A", -7.4),
    ("2016-10-06", "asc B", -6.0), ("2016-10-11", "asc A", -7.2), ("2016-10-14", "desc", -8.1),
    ("2016-10-17", "asc A", -7.0), ("2016-10-18", "asc B", -8.3)],
    "dB", "Sentinel-1 GRD via Copernicus Data Space; pole-gasawy/field-gasawy-sentinel-test.md", "real")
WET_DAY_OPS = {   # which default machine (load class) did each recorded operation (assumption: records have no machine)
    "planting": P("M2", "", "drill (sowing)"),
    "fertilisation_MINERAL": P("M1", "", "light tractor + mounted spreader"),
    "fertilisation_ORGANIC": P("M6", "", "slurry tanker"),
    "plant_protection": P("M4", "", "self-propelled sprayer"),
    "harvest": P("M5", "", "combine harvester"),
}
SENSITIVITY_VARIANTS = P([
    # (label, kind, value) - applied one at a time to the base case (spec 6.4 / pre-event sensitivity test)
    ("Base", None, None),
    ("Thresholds -0.05", "thresholds", -0.05), ("Thresholds +0.05", "thresholds", 0.05),
    ("No texture adjustment", "texture", 0.0),
    ("Transient term k = 0", "transient_k", 0.0), ("Transient term k = 0.2", "transient_k", 0.2),
    ("CAUTION = 0 day", "caution_weight", 0.0), ("CAUTION = 1 day", "caution_weight", 1.0),
    ("Rain override today >= 2 mm", "rain_today", 2.0), ("Rain override today >= 10 mm", "rain_today", 10.0),
    ("Previous-24 h override >= 5 mm", "rain_prev24", 5.0),
    ("FAO-56 evaporation (Oct-Mar)", "evaporation", "fao56"),
], "", "pre-event sensitivity test (bucket-model-test-FARM-13525.md) + FAO-56 option (17 Oct)")
# Soil of the real field, best source first (17 Oct): measured on the field > SoilGrids 250 m at the field point >
# regional NUTS3 mean (in the extracts). Fill a level with {"clay_pct", "sand_pct", "om_pct"} when you have it.
REAL_FIELD_SOIL = {
    "measured": P(None, "%", "lab soil analysis of Gasawy 28 (not provided yet)", "real"),
    "soilgrids_point": P(None, "%", "SoilGrids 2.0 250 m at the field centroid 16.64442 E, 52.59934 N, 0-30 cm "
                         "(ISRIC REST blocks automated download; enter by hand from soilgrids.org)", "modelled"),
    "centroid": P((16.64442, 52.59934), "lon, lat", "computed from pole-gasawy/gasawy_28.geojson (GUGiK ULDK)", "real"),
}

# ---------------------------------------------------------------- PROPOSED 17 Oct: tyre-based compaction check
# Simplified Terranimo-style chain (engine/compaction.py). Used only when the farmer enters the tyre inflation
# pressure; otherwise the 6.8.3 table (status x load class) stays the default. Not agreed yet: Marek + Mirela to OK.
_TN = "Terranimo introduction note (terranimo.dk, Schjønning, Lamandé, Lassen et al.)"
COMPACTION = {
    "wheels_per_axle": P(2, "wheels", "assumption: single tyres, one wheel at each end of the axle"),
    "carcass_kpa": P(15, "kPa", "assumption: mean ground pressure = inflation pressure + carcass stiffness. FRIDA "
                     "example 710/70R42 at 4.3 t: 53-75 kPa at 40-80 kPa inflation (-5...+13 kPa); measured MGP was "
                     "~36% above Terranimo (Calleja-Huerta et al. 2023, STR 233:105790) -> kept on the safe side"),
    "depths_m": P((0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8), "m", _TN + ": report depths"),
    "topsoil_max_m": P(0.25, "m", _TN + ": strength 67 kPa at 0.1-0.2 m (plough layer), 76 kPa at 0.3-0.8 m"),
    "nu_by_pf": P(((1.7, 6.0), (2.0, 5.0), (2.7, 4.0), (4.2, 3.0)), "",
                  _TN + ": Söhne (1953) concentration factor by pF (soft / firm / hard / wilting); linear in between"),
    "pf_min": P(1.0, "pF", "assumption: wettest state used (RWC_eff above 1 after rain)"),
    "pf_max": P(4.2, "pF", "permanent wilting point"),
    "pc_ref_kpa": P({"topsoil": 67.0, "subsoil": 76.0}, "kPa",
                    _TN + ": soil strength (precompression stress) at pF 2, typical bulk density; independent of clay"),
    "pc_clay_pf_slope": P(0.0294, "log10 kPa per % clay per pF unit",
                          "fitted to the 4 anchor points of the " + _TN + " (300 kPa at pF 4.2 / 3.1 and 20 kPa at "
                          "pF 0.2 / 1.1 for 10 / 20% clay); approximates, but is not, the Terranimo PTF"),
    "clay_calibrated_pct": P((4.0, 20.0), "%", "Danish strength data 4-17% clay, anchors at 10 and 20%: outside, clay "
                             "is capped and the result is flagged"),
    "sci_yellow_max": P(0.18, "SCI", _TN + ": SCI = log10(stress/strength); green <= 0, yellow up to 1.5 x strength "
                        "(~0.18), red above. (Terranimo light, Stettler et al. 2014, uses 50% / 110% borders.)"),
    "rule_stress_kpa": P(50.0, "kPa", "Schjønning et al. 2012 (Soil Use Manage.), cited by Calleja-Huerta et al. "
                         "2023: below 50 kPa at 50 cm minimises the risk of subsoil compaction"),
    "rule_depth_m": P(0.5, "m", "Schjønning et al. 2012 (see rule_stress_kpa)"),
    "min_field_bar": P(0.8, "bar", "assumption: lowest field pressure we suggest; the tyre's load/pressure table rules"),
    "pressure_step_bar": P(0.1, "bar", "search step for the 'lower tyre pressure' lever"),
    "class_to_cost_row": P({"green": "GO", "yellow": "CAUTION", "red": "NO-GO"}, "",
                           "proposed: the subsoil class (persistent damage) picks the row of the 6.8.3 table, the "
                           "axle-load class the column; tilled topsoil is usually above its strength (Terranimo note)"),
}

# ---------------------------------------------------------------- 17 Oct: NDVI productivity zones of the real field
# Pre-rendered (app/assets/ndvi_zones.png); computed once via CDSE Process API, no live call in the app.
NDVI_ZONES = {
    "method": P("Sentinel-2 L2A, NDVI 75th percentile of clear pixels (SCL 4/5) 15 Apr-30 Jun per year; years with a "
                "closed canopy only (field median >= 0.6): 2017, 2018, 2019, 2021, 2022, 2024 (2020, 2023 = spring crop); "
                "NDVI / field median per year, median over years, terciles", "", "CDSE Process API, 17 Oct", "real"),
    "zones_ha": P({"lower": 26.9, "average": 26.9, "higher": 26.9}, "ha", "terciles of 80.7 ha", "real"),
    "lower_vs_median_pct": P(-7, "%", "mean relative NDVI of the lower zone 0.93", "real"),
    "year_to_year_rank_corr": P(0.56, "Spearman", "median over year pairs (range 0.13-0.76): a moderately stable pattern", "real"),
    "corr_with_radar_wetness": P(0.0, "Spearman", "relative NDVI vs VV change 5 Oct - 29 Sep 2016: productivity zones and "
                                 "wet zones are different patterns", "real"),
}
