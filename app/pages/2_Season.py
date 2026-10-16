"""Season page (owner: Marek): P(finish by deadline), contractor, cost of delay, chart A."""
import datetime as dt

import plotly.graph_objects as go
import streamlit as st

import ui
from components import cost_cards
from engine import params as prm
from engine import stubs  # TODO: engine.season.season

ui.shell("Season")
rate = prm.MACHINES["M2"]["rate_ha_h"].value
hours = prm.CAPACITY["hours_per_day"].value
with st.expander("Inputs", expanded=True):
    c = st.columns(5)
    start = c[0].text_input("Window start (MM-DD)", prm.SEASON["window_start"].value)
    deadline = c[1].text_input("Deadline (MM-DD)", prm.SEASON["deadline"].value)
    ha_day = c[2].number_input("Own capacity (ha/day)", value=float(rate * hours), step=1.0)
    contractor = c[3].selectbox("Contractor (extra ha/day)", [0, 5, 10, 15], index=1)
    caution = c[4].radio("CAUTION counts as", list(prm.SEASON["caution_weight_options"].value),
                         index=1, horizontal=True, format_func=lambda x: f"{x} day")
params = {"window_start": start, "deadline": deadline, "ha_per_day": ha_day, "contractor_ha_day": contractor,
          "caution_weight": caution}
own = stubs.season({**params, "contractor_ha_day": 0})
with_c = stubs.season(params)

b1, b2 = st.columns(2)
with b1:
    ui.metric(f"Chance to finish by {deadline}: own machine only", f"{own['P_by_deadline']['value']:.0%}",
              own["P_by_deadline"]["origin"])
with b2:
    ui.metric(f"With contractor +{contractor} ha/day", f"{with_c['P_by_deadline']['value']:.0%}",
              with_c["P_by_deadline"]["origin"])
rec = own["contractor_recommendation"]
st.success(f"Recommendation: book a contractor for ~{rec['ha']} ha from {rec['start']} "
           f"(+{rec['extra_ha_day']} ha/day) to reach {rec['p_with']:.0%}.")
ui.show_origin(rec["origin"])

st.subheader("Cost of delay")
cost_cards.render()

st.subheader("Completion date per weather year")
comp = with_c["completion"]
base = dt.date(2016, 9, 30)   # x axis in days since 30 Sep; labels are dates (year-independent)
days = [(d.replace(year=2016) - base).days for d in comp.completion_date]
dl = (dt.date(2016, *map(int, deadline.split("-"))) - base).days
fig = go.Figure(go.Bar(y=[str(y) for y in comp.year], x=days, orientation="h",
                       marker_color=["#d73027" if d > dl else "#1a9850" for d in days],
                       text=[d.strftime("%d %b") for d in comp.completion_date], textposition="outside"))
fig.add_vline(x=dl, line_dash="dash", annotation_text=f"deadline {deadline}")
ticks = list(range(0, 36, 5))
fig.update_layout(height=380, margin=dict(l=10, r=10, t=10, b=10), xaxis=dict(
    tickvals=ticks, ticktext=[(base + dt.timedelta(days=t)).strftime("%d %b") for t in ticks]),
    yaxis=dict(autorange="reversed"), showlegend=False)
st.plotly_chart(fig, width="stretch")
ui.show_origin(with_c["completion"].origin.iloc[0])
st.caption("10 weather scenarios = AgERA5 2015-2024 for PL415. Capacity and thresholds are editable assumptions.")

s = own["sensitivity"]
st.caption(f"Sensitivity: P = {s[0.5]:.0%} (CAUTION = 1/2 day) · {s[0.0]:.0%} if CAUTION = 0 · {s[1.0]:.0%} if CAUTION = 1")

st.subheader("Parcel order")
st.dataframe(own["parcel_order"], hide_index=True)
