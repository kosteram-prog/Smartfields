"""'Find a safer plan' cards (spec 7.8; Mirela's slice, written by Marek's agent)."""
import pandas as pd
import streamlit as st

import config
import ui

REAL = config.data_dir_or_none() is not None


@st.cache_data(show_spinner="Looking for a safer plan...")
def _plans(parcel_id, date, machine_id, load_pct, passes, operation):
    from engine.plan import safer_plan
    return safer_plan(parcel_id, date, machine_id, load_pct, passes, operation)


def render(parcel_id, date, machine_id, load_pct, passes, operation="sowing") -> None:
    if not REAL:
        from engine import stubs
        plans = stubs.safer_plan(parcel_id, date, machine_id, load_pct, passes)
    else:
        plans = _plans(parcel_id, pd.Timestamp(date), machine_id, load_pct, passes, operation)
    if not plans:
        st.info("No safer plan needed: this choice is already GO (or no better option within the levers).")
        return
    cols = st.columns(len(plans))
    for col, p in zip(cols, plans):
        with col, st.container(border=True):
            st.markdown(("⭐ **Recommended** · " if p.get("recommended") else "") + f"**{p['lever'].replace('parcel', 'plot').capitalize()}**")
            ui.status_tile(f"{p.get('machine_id', '')} · {ui.field_name(p['parcel_id'])} · {pd.Timestamp(p['date']):%d %b} · "
                           f"{p['load_pct']}% load", p["status"],
                           size="1.4rem")
            st.write(ui.humanize(p["reason"]))
            alts = p.get("alternatives") or []
            if alts:
                st.caption("Also: " + ", ".join(f"{ui.field_name(a['parcel_id'])} ({a['status']})" for a in alts))
            st.write(f"Cost of this plan: {ui.fmt_eur(p['cost']['eur'])}"
                     + (f" ({p['cost']['note']})" if p["cost"].get("note") else ""))
            ui.show_origin(p["cost"]["origin"], not REAL)
