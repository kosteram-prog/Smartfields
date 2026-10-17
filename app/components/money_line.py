"""'If you wait' money line under the Today status tile (spec 7.15; Mirela's slice, written by Marek's agent)."""
import streamlit as st

import config
import ui

REAL = config.data_dir_or_none() is not None


@st.cache_data(show_spinner=False)
def _wait(date, params):
    from engine.cost import wait_cost
    return wait_cost(date, params)


def render(date, params=None) -> None:
    if not REAL:
        from engine import stubs
        w = stubs.wait_cost(date, params)
        st.markdown(f"**If you wait: {ui.fmt_eur(w['eur'])}**")
        ui.show_origin(w["origin"], True)
        return
    w = _wait(date, params or {})
    if w["eur"] == "not available":
        st.caption(w.get("message", "If you wait: not available"))
        return
    st.markdown(f"**If you wait one day: {ui.fmt_eur(w['eur'])}** "
                f"<small>(range {ui.fmt_eur(w['eur_low'])} - {ui.fmt_eur(w['eur_high'])})</small>", unsafe_allow_html=True)
    if w.get("message"):
        st.caption(w["message"])
    ui.show_origin(w["origin"], False)
