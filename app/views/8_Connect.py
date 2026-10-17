"""Integrations page: data sources in use today, and planned integrations (roadmap, nothing connected)."""
from __future__ import annotations

import streamlit as st

import ui
from engine import params as prm

ui.shell("Integrations")
st.caption("What FieldGo already uses, and which farm systems it is designed to connect to next. "
           "No vendor connection is built in this prototype and no partner credentials are stored.")

st.markdown("#### In use in this prototype")
for name, use in prm.INTEGRATIONS["in_use"].value:
    st.markdown(f"{ui.origin_badges('real')} **{name}**: {use}", unsafe_allow_html=True)

st.markdown("#### Planned integrations")
cols = st.columns(2)
for i, p in enumerate(prm.INTEGRATIONS["partners"].value):
    with cols[i % 2], st.container(border=True):
        st.markdown(f"**{p['name']}** <span style='background:#e8eaed;color:#444;border-radius:10px;padding:1px 8px;"
                    f"font-size:0.72rem;margin-left:6px'>roadmap</span>", unsafe_allow_html=True)
        st.markdown(f"Why: {p.get('use', '')}")
        st.caption("Data: " + " · ".join(p["flows"]))
        st.caption(f"Access: {p['auth']}")
st.caption("A real deployment would complete the vendor login (OAuth) in a secure backend; the farmer chooses what "
           "is shared.")
