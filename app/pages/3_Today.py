"""Today page (owner: Marek, spec 9.3): status tile, 72-h strip, reasons, confidence + Mirela's components."""
import pandas as pd
import streamlit as st

import config
import ui
from components import mark_done, money_line, plan_card, zones_panel
from engine import params as prm

replay = ui.shell("Today")
REAL = config.data_dir_or_none() is not None
if REAL:
    from engine import data
    from engine.today import today as run_today

    @st.cache_data
    def parcels(holding):
        f = data.load_farm(holding)
        f["autumn"] = f.crop.isin(["BARL", "COWT", "RAPE"])
        return f.sort_values(["autumn", "clay_pct"], ascending=[False, False])
else:
    from engine import stubs
    from engine.stubs import today as run_today
    st.warning("FIELDGO_DATA_DIR is not set: showing stub numbers.")

    def parcels(holding):
        return stubs.load_farm(holding)


@st.cache_data
def assess(parcel, date, machine, load, passes, operation, observation):
    return run_today(parcel, date, machine, load, passes, operation, **({"observation": observation} if REAL else {}))


farm = parcels(st.session_state["farm"])
label = {r.parcel_id: f"{r.parcel_id} · {r.crop} · {r.area_ha:.1f} ha · clay {r.clay_pct:.0f}%" for r in farm.itertuples()}
c = st.columns([3, 1.4, 2.4, 1.6, 1])
parcel = c[0].selectbox("Parcel", list(farm.parcel_id), format_func=label.get,
                        index=list(farm.parcel_id).index("PARCEL-0149869") if "PARCEL-0149869" in set(farm.parcel_id) else 0)
operation = c[1].selectbox("Operation", ["sowing", "fertilising", "spraying"])
machine = c[2].selectbox("Machine", list(prm.MACHINES), index=1,
                         format_func=lambda m: f"{m}: {prm.MACHINES[m]['profile']}")
load = c[3].slider("Load (%)", 0, 100, 100)
passes = c[4].number_input("Passes", 1, int(prm.PASSES["max_passes"].value), 1)
observation = st.text_input("Your observation (optional)", placeholder="e.g. ball test: soil crumbles / soil ribbons",
                            help="A hand test on the wettest spot raises confidence")

t = assess(parcel, pd.Timestamp(replay), machine, load, int(passes), operation, observation or None)
stub = not REAL

left, right = st.columns([1, 2])
with left:
    ui.status_tile(f"{parcel} · {pd.Timestamp(replay):%d %b %Y}", t["status"], size="3rem")
    ui.show_origin(t["origin"], stub)
    a, s = st.columns(2)
    with a:
        ui.status_tile("Field access", t["access"], size="1.3rem")
    with s:
        ui.status_tile("Operation suitability", t["suitability"], size="1.3rem")
    st.caption(f"{machine} at {load}% load -> axle load {t.get('axle_load_t')} t, class {t.get('load_class')} "
               "(default machine profile, assumption)")
    money_line.render(replay)
with right:
    st.markdown("**Next 72 hours** (replay: historical weather plays the forecast)")
    cols = st.columns(3)
    for col, d in zip(cols, t["strip72"]):
        with col:
            ui.status_tile(pd.Timestamp(d["date"]).strftime("%a %d %b"), d["status"], size="1.3rem")
    first = t.get("days_to_first_go")
    if first is not None:
        st.caption("First GO: " + ("today" if first == 0 else f"in {first} day(s)" if isinstance(first, int) else str(first)))
    st.markdown("**Why**")
    for r in t["reasons"]:
        st.markdown(f"- {r}")
    cond = t.get("conditions") or {}
    if cond:
        st.caption(f"Soil RWC_eff {cond['rwc_eff']:.2f} (modelled) · rain today {cond['precip_mm']:.1f} mm, last 48 h "
                   f"{cond['precip_last48h_mm']:.1f} mm · Tmax {cond['tmax_c']:.1f} °C · wind {cond['wind_m_s']:.1f} m/s (real, regional)")
    with st.container(border=True):
        conf = t["confidence"]
        st.markdown(f"**Data quality: {t.get('data_quality', 'medium')} · Confidence: "
                    f"{conf if isinstance(conf, str) else f'{conf}%'}**")
        st.caption("Based on: " + "; ".join(t["based_on"]))
        st.caption("Missing: " + "; ".join(t["missing"]))
        st.markdown(f"**Best next check:** {t['best_next_check']}")
        ui.show_origin("assumption", stub)

if st.button("Find a safer plan"):
    plan_card.render(parcel, replay, machine, load, int(passes))
mark_done.render(t, parcel, operation)
zones_panel.render()
if REAL:
    st.caption(f"Day-status rules from: {t.get('status_source')}")
