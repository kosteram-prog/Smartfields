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
    holding = st.radio("Holding", [prm.DEMO["holding_id"].value, prm.DEMO["organic_holding_id"].value],
                       horizontal=True, format_func=lambda h: h + (" (organic, rule R2)" if h.endswith("16285") else ""))
    record_check.render(holding, 2024)
