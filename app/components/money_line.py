"""Owner: Mirela. 'If you wait' money line under the status tile (stub version)."""
import streamlit as st

import ui
from engine import stubs  # TODO: engine.cost.wait_cost


def render(date, params=None) -> None:
    w = stubs.wait_cost(date, params)
    st.markdown(f"**If you wait: {ui.fmt_eur(w['eur'])}**"
                + ("" if w["days_to_first_go"] == "not available" else f" (first GO in {w['days_to_first_go']} day)"))
    ui.show_origin(w["origin"])
