"""Records page (owner: Marek). Tab 'New records' = Mirela's component, 'Record check' = Marek's."""
import streamlit as st

import ui
from components import new_records, record_check
from engine import params as prm

ui.shell("Records")
tab_new, tab_check = st.tabs(["New records", "Record check"])
with tab_new:
    new_records.render()
with tab_check:
    c = st.columns([2, 1])
    holding = c[0].radio("Holding", [prm.DEMO["holding_id"].value, prm.DEMO["organic_holding_id"].value],
                         horizontal=True,
                         format_func=lambda h: h + (" (organic example, rule R2)" if h.endswith("16285") else " (demo farm)"))
    campaign = c[1].selectbox("Campaign", [2024, None] + list(range(2026, 2016, -1)),
                              format_func=lambda y: "All 2017-2026" if y is None else str(y))
    record_check.render(holding, campaign)
