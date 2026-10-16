"""Today page (owner: Marek): status tile, 72-h strip, reasons, confidence + Mirela's components."""
import streamlit as st

import ui
from components import mark_done, money_line, plan_card, zones_panel
from engine import params as prm
from engine import stubs  # TODO: engine.today.today

replay = ui.shell("Today")
farm = stubs.load_farm(st.session_state["farm"])
c = st.columns(5)
parcel = c[0].selectbox("Parcel", farm.parcel_id)
operation = c[1].selectbox("Operation", ["sowing", "fertilising", "spraying"])
machine = c[2].selectbox("Machine", list(prm.MACHINES), index=1,
                         format_func=lambda m: f"{m}: {prm.MACHINES[m]['profile']}")
load = c[3].slider("Load (%)", 0, 100, 100)
passes = c[4].slider("Passes", 1, 3, 1)

t = stubs.today(parcel, replay, machine, load, passes, operation)
left, right = st.columns([1, 2])
with left:
    ui.status_tile(f"{parcel} · {replay}", t["status"], size="3rem")
    ui.show_origin(t["origin"])
    a, s = st.columns(2)
    with a:
        ui.status_tile("Access", t["access"], size="1.3rem")
    with s:
        ui.status_tile("Suitability", t["suitability"], size="1.3rem")
    st.caption(f"Axle load class {t.get('load_class')} ({t.get('axle_load_t')} t)")
    money_line.render(replay)
with right:
    st.markdown("**Next 72 hours (replay)**")
    cols = st.columns(3)
    for col, d in zip(cols, t["strip72"]):
        with col:
            ui.status_tile(str(d["date"]), d["status"], size="1.3rem")
    st.markdown("**Reasons**")
    for r in t["reasons"]:
        st.markdown(f"- {r}")
    st.markdown(f"**Confidence: {t['confidence']}%** (regional weather, synthetic soil, default machine)")
    ui.show_origin("assumption")
    st.caption("Based on: " + "; ".join(t["based_on"]))
    st.caption("Missing: " + "; ".join(t["missing"]))
    st.caption("Best next check: " + str(t["best_next_check"]))

if st.button("Find a safer plan"):
    plan_card.render(parcel, replay, machine, load, passes)
mark_done.render(t, parcel, operation)
zones_panel.render()
