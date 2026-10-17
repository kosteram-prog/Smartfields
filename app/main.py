"""FieldGo entry page. Run from the repo root: streamlit run app/main.py"""
import pandas as pd
import streamlit as st

import config
import ui

replay = ui.shell("FieldGo")
REAL = config.data_dir_or_none() is not None
st.subheader("Plan the season. Decide today. Keep clean records.")


@st.cache_data(show_spinner="Loading...")
def headline(date):
    if REAL:
        from engine.lint import lint_records
        from engine.season import season
        from engine.today import today
        return season({}), today("PARCEL-0149869", date, "M2", 100, 1, "sowing"), lint_records("FARM-13525", 2024)
    from engine import stubs
    return stubs.season({}), stubs.today("PARCEL-0149869", date, "M2", 100), stubs.lint_records()


s, t, r = headline(pd.Timestamp(replay))
c1, c2, c3 = st.columns(3)
with c1, st.container(border=True):
    st.markdown("#### Season")
    st.write("Will I finish autumn sowing by my deadline? Do I need a contractor? What does delay cost?")
    ui.metric("Chance to finish by 15 Oct", f"{s['P_by_deadline']['value']:.0%}", s["P_by_deadline"]["origin"], not REAL)
with c2, st.container(border=True):
    st.markdown("#### Today")
    st.write("Can I go on this parcel today with this machine and load? What if I wait?")
    ui.status_tile(f"PARCEL-0149869 (clay 55%) with M2, {pd.Timestamp(replay):%d %b %Y}", t["status"], size="1.8rem")
    ui.show_origin(t["origin"], not REAL)
with c3, st.container(border=True):
    st.markdown("#### Records")
    st.write("Mark work as done with its conditions; find the root causes of errors in past records.")
    ui.metric("2024 campaign: flags -> root causes", f"{r['n_flags']} -> {r.get('n_root_causes', len(r['cards']))}",
              r["origin"], not REAL)
st.caption("Use the pages in the sidebar. Every number carries its data origin.")
