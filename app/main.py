"""FieldGo entry page (owner: Mirela). Run from the repo root: streamlit run app/main.py"""
import streamlit as st

import ui
from engine import stubs  # TODO: real engine

replay = ui.shell("FieldGo")
st.subheader("Plan the season. Decide today. Keep clean records.")
season = stubs.season({})
c1, c2, c3 = st.columns(3)
with c1, st.container(border=True):
    st.markdown("#### Season")
    st.write("Will I finish autumn sowing by my deadline? Do I need a contractor? What does delay cost?")
    ui.metric("Chance to finish by 15 Oct", f"{season['P_by_deadline']['value']:.0%}", season["P_by_deadline"]["origin"])
with c2, st.container(border=True):
    st.markdown("#### Today")
    st.write("Can I go on this parcel today with this machine and load? What if I wait?")
    t = stubs.today("PARCEL-0149869", replay, "M2", 100)
    ui.status_tile(f"PARCEL-0149869 with M2, {replay}", t["status"], size="1.8rem")
    ui.show_origin(t["origin"])
with c3, st.container(border=True):
    st.markdown("#### Records")
    st.write("Mark work as done with its conditions; find the root causes of errors in past records.")
    r = stubs.lint_records()
    ui.metric("2024 campaign: flags -> root causes", f"{r['n_flags']} -> {len(r['cards'])}", r["origin"])
st.caption("Use the pages in the sidebar. Every number carries its data origin; stub badges disappear as real engine functions replace the stubs.")
