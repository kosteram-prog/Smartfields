"""Owner: Mirela. 'Find a safer plan' card for the Today page (stub version)."""
import streamlit as st

import ui
from engine import stubs  # TODO: engine.plan.safer_plan


def render(parcel_id, date, machine_id, load_pct, passes) -> None:
    plans = stubs.safer_plan(parcel_id, date, machine_id, load_pct, passes)
    cols = st.columns(len(plans))
    for col, p in zip(cols, plans):
        with col, st.container(border=True):
            st.markdown(f"**{p['lever'].capitalize()}**")
            ui.status_tile(f"{p['parcel_id']} - {p['date']}", p["status"], size="1.5rem")
            st.write(p["reason"])
            st.write(f"Cost of this plan: {ui.fmt_eur(p['cost']['eur'])}")
            ui.show_origin(p["cost"]["origin"])
