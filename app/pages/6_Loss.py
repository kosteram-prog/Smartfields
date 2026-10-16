"""Loss calculator page (owner: Mirela): euro impact if you enter wet / delayed fields."""
from __future__ import annotations

import datetime as dt

import streamlit as st

import ui
from engine import params as prm
from engine import stubs

ui.shell("Loss calculator")
st.caption(
    "Per-farm estimate for a chosen entry period. Every percentage is labelled "
    "as an assumption — not a measured yield trial on this holding."
)

fs = stubs.farm_summary(st.session_state["farm"])
uaa = float(fs["uaa_ha"])
eur_ha = float(prm.LOSS_CALC["demo_output_eur_ha"].value)
annual_output = uaa * eur_ha

c1, c2, c3 = st.columns(3)
with c1:
    ui.metric("Farm UAA", f"{uaa:.0f} ha", fs["origin"])
with c2:
    ui.metric("Assumed output", ui.fmt_eur(annual_output),
              prm.LOSS_CALC["demo_output_eur_ha"].origin)
with c3:
    ui.metric("EUR / ha (assumption)", f"{eur_ha:,.0f}",
              prm.LOSS_CALC["demo_output_eur_ha"].origin)

st.subheader("Entry scenario")
status = st.selectbox(
    "Field status",
    ["Soil too wet (compaction risk)", "Delayed field entry", "Wet soil + delay"],
)
share = st.slider(
    "Share of farm entered (%)",
    1, 100, int(prm.LOSS_CALC["default_entered_share_pct"].value),
)
today = st.session_state["replay_date"]
col_a, col_b = st.columns(2)
with col_a:
    start = st.date_input("Period from", value=today - dt.timedelta(days=3))
with col_b:
    end = st.date_input("Period to", value=today)

days = max(1, (end - start).days + 1)
entered = annual_output * (share / 100.0)
compaction_pct = float(prm.LOSS_CALC["recare_compaction_pct"].value)
delay_pct = float(prm.LOSS_CALC["delay_pct_per_day"].value)

compaction = delay = 0.0
if "wet" in status.lower() or status.startswith("Wet"):
    compaction = entered * (compaction_pct / 100.0)
if "delay" in status.lower() or "Delayed" in status:
    delay = entered * (delay_pct / 100.0) * days
total = compaction + delay
per_ha = total / max(uaa * share / 100.0, 1e-9)

st.markdown("---")
st.metric("Estimated euro loss", ui.fmt_eur(total))
ui.show_origin("assumption", stub=False)
st.write(
    f"{share}% of {fs['holding_id']} · {uaa * share / 100:.0f} ha · "
    f"{days} day(s) ({start} → {end})"
)
if compaction:
    st.write(
        f"- Compaction scenario ({compaction_pct}% of entered output): "
        f"**{ui.fmt_eur(compaction)}** — {prm.LOSS_CALC['recare_compaction_pct'].source}"
    )
if delay:
    st.write(
        f"- Delay scenario ({delay_pct}% × {days} d): "
        f"**{ui.fmt_eur(delay)}** — {prm.LOSS_CALC['delay_pct_per_day'].source}"
    )
st.write(f"- ≈ {ui.fmt_eur(per_ha)} per hectare entered")

with st.expander("Assumptions (labelled)"):
    st.markdown(
        f"""
- **Compaction %** = `{compaction_pct}` — origin `{prm.LOSS_CALC['recare_compaction_pct'].origin}`
  ({prm.LOSS_CALC['recare_compaction_pct'].source}).
- **Delay % / day** = `{delay_pct}` — origin `{prm.LOSS_CALC['delay_pct_per_day'].origin}`
  ({prm.LOSS_CALC['delay_pct_per_day'].source}).
- **Output base** = UAA × `{eur_ha}` EUR/ha stub assumption
  (`LOSS_CALC.demo_output_eur_ha`) because organisers' economics are not loaded here.
- Related shared tables (unchanged): `COST.loss_rate_pct_per_day`, `WET_TRAFFIC_LOSS`.
"""
    )
