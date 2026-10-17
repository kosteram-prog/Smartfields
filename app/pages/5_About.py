"""About the data and AI (spec 9.5): sources and origin labels, assumption tables, confidence, AI statement, limits."""
import pandas as pd
import streamlit as st

import ui
from engine import params as prm

ui.shell("About the data and AI")
st.markdown("""
FieldGo is a **deterministic** decision aid. Every GO / CAUTION / NO-GO and every number comes from transparent
rules and published equations applied to the listed data. Every number in the app carries its **origin**.
""")
st.subheader("Data and origin labels")
st.table(pd.DataFrame([
    {"origin": "real", "data": "AgERA5 daily weather 2015-2024 (Copernicus C3S), regional NUTS3 average", "use": "Soil water, statuses, Season scenarios, N check, record conditions"},
    {"origin": "modelled", "data": "Our engine: Saxton-Rawls soil hydraulics, 0-30 cm soil-water bucket, statuses, season simulation", "use": "Every status and probability"},
    {"origin": "synthetic", "data": "Organisers' farm FARM-13525: parcels, parcel soil, operations, yields, prices", "use": "Farm, records, expected yield and price"},
    {"origin": "assumption", "data": "Parameter tables below (editable), each with its source", "use": "Thresholds, machines, loss rates"},
    {"origin": "real (satellite)", "data": "Sentinel-1 radar over a real 80.7 ha field near Poznań (Oct 2016), pre-rendered", "use": "Field zones panel"},
]))

st.subheader("Assumption tables (prototype values, reviewed by the team's agronomists)")
tabs = st.tabs(["Machines 6.1", "Thresholds 6.4", "Cost of delay 6.8", "Wet traffic 6.8.3", "N check 6.7", "Confidence 7.9"])
with tabs[0]:
    st.dataframe(pd.DataFrame([{"id": k, "profile": v["profile"], "max axle loaded (t)": v["max_axle_t"].value,
                                "class at full load": v["load_class"], "work rate (ha/h)": v["rate_ha_h"].value,
                                "empty share": v["empty_share"].value} for k, v in prm.MACHINES.items()]), hide_index=True)
    st.caption("Classes by max axle load: L1 < 4 t, L2 4-6 t, L3 6-8 t, L4 8-10 t, L5 > 10 t. Source to verify: "
               "manufacturer data, KTBL, Terranimo. Your own machine can be entered on the Today page.")
with tabs[1]:
    st.dataframe(pd.DataFrame([{"class": k, "GO if RWC_eff <=": v["go"].value, "CAUTION if <=": v["caution"].value}
                               for k, v in prm.THRESHOLDS.items()]), hide_index=True)
    st.caption("Texture: clay >= 30 % -0.05, sand >= 70 % +0.05; each extra pass -0.03; rain today >= 5 mm -> NO-GO; "
               ">= 10 mm in the previous 24 h -> at best CAUTION; frozen soil carries L1-L3; no fertilising on frozen "
               "soil. RWC_eff = RWC + 0.1 x min(1, rain in the last 48 h / 20 mm). Support: Smedema (1979), AHDB.")
with tabs[2]:
    c = prm.COST
    st.dataframe(pd.DataFrame([{"crop": k, "optimal sowing ends": v.value or "enter manually", "source": v.source}
                               for k, v in c["optimum_end"].items()]), hide_index=True)
    st.caption(f"Loss rate {c['loss_rate_pct_per_day']['low'].value} / {c['loss_rate_pct_per_day']['default'].value} / "
               f"{c['loss_rate_pct_per_day']['high'].value} % of yield per day after the optimal date (IUNG, Jończyk), "
               f"cap {c['loss_cap_pct'].value} %. Contractor price {c['contractor_price_eur_ha'].value} EUR/ha "
               f"({c['contractor_price_eur_ha'].source}). Headline = weather part; late start shown separately.")
with tabs[3]:
    w = prm.WET_TRAFFIC_LOSS
    st.dataframe(pd.DataFrame([{"class": k, "NO-GO year-1 loss %": w["NO-GO"][k].value,
                                "CAUTION year-1 loss %": w["CAUTION"][k].value} for k in w["NO-GO"]]), hide_index=True)
    st.caption(f"Applied to {w['trafficked_share'].value:.0%} of the parcel (trafficked share, editable). Anchor: "
               "Håkansson multi-site study (10-12 t axle ~15 % year-1 loss; 3-5 % subsoil losses for 12 years). "
               "L3/L4 and the CAUTION factor are interpolated: illustrative, needs calibration.")
with tabs[4]:
    n = prm.N_RULES
    st.markdown(f"- **High:** any day >= {n['heavy_rain']['rain_mm'].value:g} mm from the application day to "
                f"+{n['heavy_rain']['days'].value} days -> {n['heavy_rain']['n_at_risk_pct'].value[0]}-"
                f"{n['heavy_rain']['n_at_risk_pct'].value[1]} % of the N at risk\n"
                f"- **Medium:** < {n['no_uptake']['rain_mm_lt'].value:g} mm in the next {n['no_uptake']['days'].value} "
                f"days -> {n['no_uptake']['n_at_risk_pct'].value[0]}-{n['no_uptake']['n_at_risk_pct'].value[1]} %\n"
                "- **Prohibited:** closed period (default 1 Dec - 31 Jan, verify per country) or frozen soil\n"
                "Indicative ranges, labelled 'prototype'.")
with tabs[5]:
    st.dataframe(pd.DataFrame([{"item": k.replace("_", " "), "points": v.value} for k, v in prm.CONFIDENCE.items()]),
                 hide_index=True)
    st.caption("Start at 100 and subtract for each indirect or missing input. A farmer observation (hand test) and "
               "your own machine data raise confidence.")
ui.show_origin("assumption", False)

st.subheader("AI transparency")
st.info("We used AI coding assistants to build the prototype. All decisions in FieldGo come from transparent rules and "
        "published equations applied to the listed data. An optional AI component rewrites explanations of computed "
        "results in plain language; it cannot change any value or decision (checked in code, labelled "
        "'AI-written explanation').")
st.subheader("Limitations")
st.markdown("""
- Weather is a **regional** daily average (NUTS3), not field-level; replay mode uses history as the forecast.
- Parcel soil and all farm records are **synthetic**; synthetic yields and prices do not react to weather.
- Thresholds, machine profiles and loss rates are **prototype assumptions** from published sources, not calibrated
  field rules; the 2016 cost of delay changes several-fold across reasonable assumptions, so it is always a range.
- The soil-water model is a simple 0-30 cm bucket; it cannot see subsoil wetness or bearing capacity.
""")
