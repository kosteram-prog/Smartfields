"""Connect page (owner: Mirela): API integration points — not live vendor logins."""
from __future__ import annotations

import streamlit as st

import ui
from engine import params as prm

ui.shell("Connect")
st.caption(
    "FieldGo can integrate via API with farm systems. These controls are "
    "**connection points** only — this demo does not complete OAuth, does not "
    "call private vendor APIs, and does not import partner data."
)

st.info(
    "No partner credentials are stored in the repository. A real deployment "
    "would finish OAuth in a secure backend, then pull the data listed below.",
    icon="🔌",
)

partners = prm.INTEGRATIONS["partners"].value
choice = st.radio(
    "Partner",
    options=[p["id"] for p in partners],
    format_func=lambda i: next(p["name"] for p in partners if p["id"] == i),
    horizontal=True,
)
partner = next(p for p in partners if p["id"] == choice)

if st.button(f"Connect — {partner['name']}", type="primary"):
    st.session_state["connect_partner"] = partner["id"]

selected = st.session_state.get("connect_partner")
if selected == partner["id"]:
    st.success(f"{partner['name']} — ready to connect (no live login performed).")
    st.write(f"**Auth path:** {partner['auth']}")
    st.write("**Data that would flow after a real connection:**")
    for item in partner["flows"]:
        st.write(f"- {item}")
    st.caption("Status: connection point only — not linked to a live account.")
    ui.show_origin("assumption", stub=False)
else:
    st.write("Choose a partner and press **Connect** to see the planned data flows.")

with st.expander("All partners at a glance"):
    for p in partners:
        st.markdown(f"**{p['name']}** — {p['auth']}")
        st.caption(" · ".join(p["flows"]))
