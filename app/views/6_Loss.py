"""Loss calculator: what does it cost to drive on the wet plots today, compared with waiting a day?

Every number comes from the same engine as Season and Today:
  go now        -> engine.cost.go_now_cost (axle load x tyres x how wet the soil is; subsoil from the compaction check)
  wait one day  -> engine.cost.wait_cost  (season cost of delay with the day skipped, whole farm, replay year)
"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import config
import ui
from engine import params as prm

replay = ui.shell("Loss calculator")
st.caption("Drive on the wet plots today, or wait? Both answers in euro, from the same engine as Today and Season. "
           "Change the machine, the tyres or the tramlines and watch the numbers move. Illustrative values: synthetic "
           "yield and price, loss rates from published anchors, to calibrate in pilots.")
if config.data_dir_or_none() is None:
    st.warning("FIELDGO_DATA_DIR is not set: the loss calculator needs the data extracts.")
    st.stop()

from engine import data, season, soil, status  # noqa: E402
from engine.cost import day_plan_cost, default_economics, go_now_cost, wait_cost  # noqa: E402

M = prm.GO_NOW_MODEL
Y1, SUB = "#2a78d6", "#e87ba4"            # validated pair (dataviz validator): year 1 / subsoil years

c = st.columns(4)
machine = ui.pick(c[0], "selectbox", "Machine", "machine", list(prm.MACHINES),
                  format_func=lambda m: f"{m}: {prm.MACHINES[m]['profile']}")
load = ui.pick(c[1], "slider", "Load (%)", "load", min_value=0, max_value=100)
operation = ui.pick(c[2], "selectbox", "Operation", "operation", ["sowing", "fertilising", "spraying"])
lc0, _ = status.axle_load_class(machine, load)
bar = c[3].slider("Tyre pressure (bar)", 0.6, 3.0, float(M["default_tyre_bar"].value.get(lc0, 1.4)), 0.1,
                  key=f"loss_bar_{lc0}", help="Default: typical for this axle load. Lower = bigger footprint.")
c = st.columns([1, 1, 2])
share = c[0].slider("Share of each plot under the wheels (%)", 10, 100,
                    int(prm.WET_TRAFFIC_LOSS["trafficked_share"].value * 100), 5,
                    help="Lower with tramlines / controlled traffic, higher with headland turning.")
price_adj = c[1].slider("Grain price vs default (%)", 50, 150, 100, 10)


@st.cache_data(show_spinner="Soil water of every plot...")
def _day(holding, date, operation):
    farm = data.load_farm(holding)
    pool = farm[farm.crop.isin(season.autumn_crops())] if operation == "sowing" else farm
    sw = soil.soil_water(pool, data.load_weather(pool.nuts3.iloc[0]))
    return pool, sw[sw.date == pd.Timestamp(date)]


@st.cache_data(show_spinner=False)
def _table(holding, date, operation, machine, load, bar, share, price_adj, default_bar=False):
    pool, sw = _day(holding, date, operation)
    lc, axle = status.axle_load_class(machine, load)
    stt = status.status_table(sw, pool, lc, 1, operation).set_index("parcel_id")
    rwc = sw.set_index("parcel_id")["RWC_eff"]
    econ = default_economics(holding)
    econ = {"yield_t_ha": econ["yield_t_ha"], "trafficked_share": share / 100,
            "price_eur_t": {k: v * price_adj / 100 for k, v in econ["price_eur_t"].items()}}
    b = M["default_tyre_bar"].value.get(lc, 1.4) if default_bar else bar
    rows = []
    for r in pool.itertuples():
        s_ = stt.status.get(r.parcel_id, "not available")
        e = go_now_cost(s_, rwc.get(r.parcel_id), axle, lc, r.clay_pct, r.sand_pct, getattr(r, "om_pct", None),
                        r.crop, r.area_ha, b, 1, econ)
        rows.append({"plot": ui.field_name(r.parcel_id), "parcel_id": r.parcel_id, "crop": ui.CROP_WORDS.get(r.crop, r.crop),
                     "area_ha": r.area_ha, "clay_pct": r.clay_pct, "status": s_, "rwc_eff": rwc.get(r.parcel_id),
                     "year1_eur": e["eur"], "subsoil_eur_per_year": e.get("persistent_eur_per_year"),
                     "subsoil_eur_total": e.get("persistent_eur_total"), "loss_pct": e.get("loss_pct"),
                     **{f"f_{k}": v for k, v in (e.get("drivers") or {}).items()}})
    return pd.DataFrame(rows), lc, axle


holding, day = st.session_state["farm"], pd.Timestamp(replay)
t, lc, axle = _table(holding, day, operation, machine, load, bar, share, price_adj)
for col in ("year1_eur", "subsoil_eur_per_year", "subsoil_eur_total"):
    t[col] = pd.to_numeric(t[col], errors="coerce")
wet = t[t.status.isin(["CAUTION", "NO-GO"])]
st.caption(f"{day:%d %b %Y} · {prm.MACHINES[machine]['profile']} at {load}% → {axle} t on the heaviest axle "
           f"(class {lc}), {bar:.1f} bar · {len(wet)} of {len(t)} plots are CAUTION / NO-GO today")

# ------------------------------------------------------------------ headline: today's plan for this machine, in euro
y1, sub_y, sub_t = wet.year1_eur.sum(), wet.subsoil_eur_per_year.sum(), wet.subsoil_eur_total.sum()
if operation == "sowing":
    w = wait_cost(day, {"machine_id": machine})
    if isinstance(w.get("eur"), (int, float)):
        w = w | {"eur": round(w["eur"] * price_adj / 100, 0)}
else:
    w = {"eur": "not available", "message": "Waiting cost is modelled for autumn sowing only."}
cap = prm.MACHINES[machine]["rate_ha_h"].value * prm.CAPACITY["hours_per_day"].value
plan = day_plan_cost(t, cap, w.get("eur"))
VERD = {"go_plots_only": ("GO", "Work only the GO plots", plan.get("message", "")),
        "fill_with_wet": ("CAUTION", "Fill the day with the cheapest wet plots",
                          f"{plan['wet_ha']:.0f} ha on wet soil costs ~{ui.fmt_eur(plan['wet_eur'])}, less than "
                          f"leaving it ({ui.fmt_eur(plan['wait_part_eur'])})"),
        "go_plots_only_wait": ("NO-GO", "Work the GO plots, leave the wet ones",
                               f"{plan['wet_ha']:.0f} ha on wet soil would cost ~{ui.fmt_eur(plan['wet_eur'])}, more "
                               f"than leaving it ({ui.fmt_eur(plan['wait_part_eur'])})"),
        "close": ("CAUTION", "Close call", f"wet {ui.fmt_eur(plan['wet_eur'])} vs leaving it "
                  f"{ui.fmt_eur(plan['wait_part_eur'])}: only the driest part of the cheapest plot")}
k = st.columns([1, 1, 1, 1.3])
with k[0]:
    ui.metric("Today's capacity", f"{cap:.0f} ha", "assumption", False,
              help=f"{prm.MACHINES[machine]['rate_ha_h'].value} ha/h × {prm.CAPACITY['hours_per_day'].value} h, one unit")
    st.caption(f"GO plots today: {plan['go_ha']:.0f} ha")
with k[1]:
    ui.metric("Driving on all wet plots", ui.fmt_eur(float(y1)), "modelled+synthetic+assumption", False,
              help="Year-1 yield loss on the trafficked part of every CAUTION / NO-GO plot")
    st.caption(f"\\+ {ui.fmt_eur(float(sub_y))}/yr for ~{prm.WET_TRAFFIC_LOSS['persistent']['years'].value} yrs "
               f"(subsoil) · {wet.area_ha.sum():.0f} ha")
with k[2]:
    if isinstance(w.get("eur"), (int, float)):
        ui.metric("Wait one day (whole farm)", ui.fmt_eur(w["eur"]), w.get("origin", "modelled"), False,
                  help="Season cost of delay with this day skipped minus with it used (replay year)")
        st.caption(w.get("message") or (f"range {ui.fmt_eur(w['eur_low'])} - {ui.fmt_eur(w['eur_high'])}"
                                        if isinstance(w.get("eur_low"), (int, float)) else ""))
    else:
        st.metric("Wait one day", "not available")
        st.caption(w.get("message", ""))
with k[3]:
    if plan["verdict"] in VERD:
        col_as, word, why = VERD[plan["verdict"]]
        col = ui.STATUS_COLORS[col_as]
        st.markdown(f"<div style='border-left:6px solid {col};padding:8px 12px;background:{col}18;border-radius:8px'>"
                    f"<div style='font-size:0.8rem;opacity:0.8'>Today's plan, cheapest</div>"
                    f"<div style='font-size:1.2rem;font-weight:700;color:{col}'>{word}</div>"
                    f"<div style='font-size:0.8rem'>{why}</div></div>", unsafe_allow_html=True)
        if plan["wet_plan"]:
            st.caption("Wet plots to add: " + ", ".join(f"{ui.field_name(p['parcel_id'])} ({p['ha']:g} ha, "
                                                         f"{ui.fmt_eur(p['eur'])})" for p in plan["wet_plan"]))
    else:
        st.metric("Today's plan", "—")

# ------------------------------------------------------------------ per plot: what each wet plot would cost
left, right = st.columns([1.5, 1], gap="large")
with left:
    st.markdown("**If you drive on each wet plot today**")
    if wet.empty:
        st.info("No CAUTION / NO-GO plot today with this machine: nothing to lose from wet traffic.")
    else:
        wv = wet.assign(total=wet.year1_eur.fillna(0) + wet.subsoil_eur_total.fillna(0)).sort_values("total")
        fig = go.Figure()
        hover = [f"{r.plot} · {r.crop} · {r.area_ha:.1f} ha · clay {r.clay_pct:.0f}%<br>{r.status}, RWC {r.rwc_eff:.2f}"
                 f"<br>wetness factor {r.f_wetness:.2f} · subsoil factor {r.f_subsoil:.2f}" for r in wv.itertuples()]
        fig.add_trace(go.Bar(y=wv["plot"], x=wv.year1_eur, orientation="h", name="Year 1", marker_color=Y1,
                             hovertext=hover, hovertemplate="%{hovertext}<br>Year 1: EUR %{x:,.0f}<extra></extra>"))
        fig.add_trace(go.Bar(y=wv["plot"], x=wv.subsoil_eur_total, orientation="h", name="Subsoil, ~10 years",
                             marker_color=SUB, hovertext=hover,
                             hovertemplate="%{hovertext}<br>Subsoil, 10 yrs: EUR %{x:,.0f}<extra></extra>"))
        if isinstance(w.get("eur"), (int, float)):
            fig.add_vline(x=w["eur"], line=dict(color="#555", dash="dash", width=1.5))
            fig.add_annotation(x=w["eur"], y=1.02, yref="paper", text=f"wait one day: {ui.fmt_eur(w['eur'])}",
                               showarrow=False, font=dict(size=11, color="#555"), xanchor="left")
        fig.update_layout(barmode="stack", height=max(260, 28 * len(wv) + 90), bargap=0.25,
                          margin=dict(l=10, r=10, t=30, b=10), plot_bgcolor="white",
                          legend=dict(orientation="h", y=-0.12), xaxis=dict(title="EUR", gridcolor="#eee"))
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        st.caption("Plots left of the dashed line cost less to drive on than one day of waiting for the whole farm; "
                   "plots right of it are better left for a drier day.")
with right:
    st.markdown("**Same day, other machines** (all wet plots, default tyres)")
    rows = []
    for mid in prm.MACHINES:
        tm, lcm, axm = _table(holding, day, operation, mid, 100, 0.0, share, price_adj, default_bar=True)
        wm = tm[tm.status.isin(["CAUTION", "NO-GO"])]
        tot = pd.to_numeric(wm.year1_eur, errors="coerce").sum() + pd.to_numeric(wm.subsoil_eur_total,
                                                                                  errors="coerce").sum()
        rows.append({"machine": f"{mid} · {axm:g} t", "total": tot, "wet": len(wm), "go": int((tm.status == "GO").sum())})
    mt = pd.DataFrame(rows)
    fig2 = go.Figure(go.Bar(y=mt.machine, x=mt.total, orientation="h", marker_color=Y1,
                            text=[f"{ui.fmt_eur(x)} · {g} GO / {n} wet" for x, g, n in zip(mt.total, mt.go, mt.wet)],
                            textposition="outside", cliponaxis=False,
                            hovertemplate="%{y}: EUR %{x:,.0f} incl. subsoil years<extra></extra>"))
    fig2.update_layout(height=300, margin=dict(l=10, r=130, t=10, b=10), plot_bgcolor="white",
                       yaxis=dict(autorange="reversed"), xaxis=dict(title="EUR, year 1 + subsoil years", gridcolor="#eee"))
    st.plotly_chart(fig2, width="stretch", config={"displayModeBar": False})
    st.caption("A lighter machine has more GO plots and does less damage on the wet ones.")

with st.expander("Per plot table"):
    st.dataframe(t.sort_values(["status", "year1_eur"], ascending=[False, False])[
        ["plot", "crop", "area_ha", "clay_pct", "status", "rwc_eff", "loss_pct", "year1_eur", "subsoil_eur_per_year",
         "f_wetness", "f_axle", "f_tyre", "f_subsoil", "parcel_id"]], hide_index=True, width="stretch",
        column_config={"year1_eur": st.column_config.NumberColumn("Go now, year 1", format="EUR %,.0f"),
                       "subsoil_eur_per_year": st.column_config.NumberColumn("Subsoil, per year", format="EUR %,.0f"),
                       "area_ha": st.column_config.NumberColumn("Area (ha)", format="%.1f"),
                       "clay_pct": st.column_config.NumberColumn("Clay %", format="%.0f"),
                       "rwc_eff": st.column_config.NumberColumn("RWC", format="%.2f"),
                       "loss_pct": st.column_config.NumberColumn("Year-1 loss %", format="%.1f"),
                       "f_wetness": "wetness", "f_axle": "axle", "f_tyre": "tyre", "f_subsoil": "subsoil"})
ui.show_origin("real+modelled+synthetic+assumption", False)


@st.cache_data(show_spinner="Avoidable losses from the farm's records...")
def _avoidable(holding):
    from engine.cost import avoidable_losses
    return avoidable_losses(holding)


st.subheader("Losses FieldGo could help avoid, per year")
av = _avoidable(holding)
if isinstance(av["year1_eur_mean"], float):
    k2 = st.columns(3)
    with k2[0]:
        ui.metric("Compaction, year 1", ui.fmt_eur(av["year1_eur_mean"]), av["origin"], False,
                  help="Mean per year: recorded operations done on CAUTION / NO-GO days, worst one per plot-year")
        st.caption(f"≈ {ui.fmt_eur(av['year1_eur_mean'] / av['area_ha'])} per ha · years {av['years'][0]}-{av['years'][-1]}")
    with k2[1]:
        ui.metric("Subsoil, every year after", ui.fmt_eur(av["subsoil_eur_per_year_mean"]), av["origin"], False,
                  help="Long-term subsoil part (RECARE 2018) added by each season's wet traffic")
        st.caption(f"for ~{av['subsoil_years']} years from each season's damage")
    with k2[2]:
        d = av["delay_weather_eur_median"]
        ui.metric("Late sowing, weather part", ui.fmt_eur(d), av["origin"], False,
                  help="Median-year cost of delay caused by weather (recoverable with planning and a contractor)")
        st.caption("median year; the late-start part (rotation) is not counted")
    st.caption("Upper bound, illustrative: " + av["note"] + " Valued with the status x load-class table (records have "
               "no machine, tyre or soil-moisture data).")
else:
    st.caption("Not available for this farm (no operation records).")

with st.expander("Method and assumptions"):
    st.markdown("""
- **Status** per plot: soil-water model + thresholds by axle-load class for this machine and load.
- **Go now, year 1** = 15 % (Håkansson multi-site study: 10-12 t axles on wet soil) × axle load / 11 t × (tyre bar / 2.0)^0.5
  × wetness, on the trafficked share × area × expected yield × price. Wetness = 0 on GO; rises from the GO limit of the
  load class to 1 at RWC 1.10 (at least 0.25 on CAUTION, 0.5 on NO-GO days caused by rain).
- **Subsoil** = 6 % of yield per year (RECARE 2018) × the subsoil overstress of the compaction check (stress vs strength at
  30-80 cm, today's wetness) relative to an 11 t / 2 bar / wet clay-loam anchor, for ~10 years, undiscounted.
- **Wait one day** = season cost of delay (barley 0.43 %/day, wheat 1 %/day after the optimal sowing date) with the day
  skipped, whole farm.
- **Cheaper today**: go if go-now (incl. subsoil years) < 0.8 × wait, wait if > 1.25 × wait, otherwise close.
- Yield and price: synthetic farm data (mean 2017-2024; Jul-Aug price). Illustrative: calibrate in pilots.
""")
