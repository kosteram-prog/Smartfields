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

import config  # noqa: E402

if config.data_dir_or_none() is not None:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    from engine import sensitivity, validate

    st.subheader("Does the model agree with the satellite?")

    @st.cache_data(show_spinner="Comparing with Sentinel-1...")
    def _radar():
        return validate.radar_vs_model()

    r = _radar()
    f = r["field"]
    st.caption(f"Real field {f['name']}, {f['area_ha']} ha near Poznań, regional SoilGrids topsoil (clay {f['clay_pct']}%, "
               f"sand {f['sand_pct']}%, OM {f['om_pct']}%), AgERA5 {f['nuts3']} weather, the same soil-water model as "
               "the demo farm, compared with the field-mean Sentinel-1 radar backscatter (VV).")
    d, m = r["daily"], r["radar"]
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.06, row_heights=[0.25, 0.4, 0.35],
                        subplot_titles=("Rain (mm/day, AgERA5)", "Model: topsoil wetness RWC_eff (1 = field capacity)",
                                        "Radar: Sentinel-1 VV (dB, wetter surface = higher)"))
    fig.add_trace(go.Bar(x=d.date, y=d.rain_today_mm, marker_color="#5b8db8", name="rain",
                         hovertemplate="%{x|%d %b}: %{y:.1f} mm<extra></extra>"), row=1, col=1)
    fig.add_trace(go.Scatter(x=d.date, y=d.RWC_eff, mode="lines", line=dict(width=2, color="#6a3d9a"), name="model",
                             hovertemplate="%{x|%d %b}: RWC_eff %{y:.2f}<extra></extra>"), row=2, col=1)
    fig.add_hline(y=1.0, line_dash="dot", line_color="#888", row=2, col=1)
    same = m.orbit == "asc A"
    for mask, name, sym in ((same, "same orbit (asc A)", "circle"), (~same, "other orbits", "circle-open")):
        fig.add_trace(go.Scatter(x=m.date[mask], y=m.vv_db[mask], mode="markers", name=name,
                                 marker=dict(size=10, color="#1f6f8b", symbol=sym, line=dict(width=2, color="#1f6f8b")),
                                 hovertemplate="%{x|%d %b}: %{y:.1f} dB<extra>" + name + "</extra>"), row=3, col=1)
    fig.update_layout(height=520, margin=dict(l=10, r=10, t=40, b=10), plot_bgcolor="white",
                      legend=dict(orientation="h", y=-0.08), showlegend=True)
    fig.update_xaxes(gridcolor="#eee")
    fig.update_yaxes(gridcolor="#eee")
    st.plotly_chart(fig, width="stretch")
    st.markdown(f"- Both see the rain of 3-6 Oct: the radar rises **{r['vv_change_db']:+.1f} dB** (29 Sep -> 5 Oct), "
                f"the model goes from a dry topsoil to above field capacity.\n"
                f"- Rank correlation on all {r['n_dates']} radar dates: **{r['spearman_all']:.2f}**. On the "
                f"{r['n_same_orbit']} same-orbit dates inside the wet period it is only {r['spearman_same_orbit']:.2f}: "
                "the model dries the sandy topsoil faster than the radar suggests.\n"
                "- Radar also responds to roughness and residue, so this is *consistent with the model*, not proof.")
    ui.show_origin(r["origin"], False)

    st.subheader("How robust are the numbers? (one assumption changed at a time)")

    @st.cache_data(show_spinner="Re-running the season for 11 variants (~10 s)...")
    def _sens():
        return sensitivity.run_all()

    if st.toggle("Run the sensitivity table", value=False,
                 help="Recomputes soil water, statuses, the 10-autumn season and the cost of delay for each variant"):
        t = _sens().rename(columns={"P": "P(finish by 15 Oct)", "done_2016": "2016 done", "workable_days_2016":
                                    "workable days 1-21 Oct 2016", "contractor": "contractor for >= 90 % (ha/day)",
                                    "cost_median": "weather cost, median", "cost_2016": "weather cost, 2016",
                                    "demo_13oct": "13 Oct: clay L2/L3 · sand L2/L3"})
        st.dataframe(t, hide_index=True, width="stretch", column_config={
            "P(finish by 15 Oct)": st.column_config.NumberColumn(format="percent"),
            "weather cost, median": st.column_config.NumberColumn(format="EUR %.0f"),
            "weather cost, 2016": st.column_config.NumberColumn(format="EUR %.0f")})
        st.markdown("**Robust:** P stays 60-100 %, the median-year cost stays a few thousand euro and a contractor "
                    "helps in every variant. **Not robust:** the cost of a wet autumn like 2016 moves several-fold "
                    "with the thresholds and the CAUTION rule, so we always show it as a range. G/C/N = GO/CAUTION/NO-GO.")
        ui.show_origin("modelled+assumption", False)

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
