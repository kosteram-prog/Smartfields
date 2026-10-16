"""Owner: Mirela. Cost-of-delay and contractor cards for the Season page (stub version)."""
import streamlit as st

import ui
from engine import stubs  # TODO: switch to engine.cost when it exists


def render(schedule=None, parcels=None, params=None) -> None:
    cost = stubs.season_cost(schedule, parcels, params)
    m, w = cost["median"], cost["worst_year"]
    c1, c2, c3 = st.columns(3)
    with c1:
        ui.metric("Median cost of delay (weather part)", ui.fmt_eur(m["weather_default"]),
                  cost["origin"], help="Weather part of the yield loss, default rate 1.0 %/day")
        st.caption(f"range {ui.fmt_eur(m['weather_low'])} - {ui.fmt_eur(m['weather_high'])} (rate 0.5-1.5 %/day)")
    with c2:
        ui.metric(f"Worst year ({w['year']})", ui.fmt_eur(w["weather_default"]), cost["origin"])
        st.caption(f"range {ui.fmt_eur(w['weather_low'])} - {ui.fmt_eur(w['weather_high'])}")
    with c3:
        ui.metric("Late-start cost (separate line)", ui.fmt_eur(m["late_start_default"]), cost["origin"],
                  help="Cost of starting on 1 Oct after maize, even in perfect weather")
    cv = stubs.contractor_value(cost, cost, 60, 68)
    st.markdown(f"**Contractor (15 ha/day, ~60 ha at EUR 68/ha)** saves about {ui.fmt_eur(cv['value_median'])} in the "
                f"median year and {ui.fmt_eur(cv['value_worst'])} in {cv['worst_year']}; "
                f"net in {cv['worst_year']}: {ui.fmt_eur(cv['net_benefit_worst'])}.")
    ui.show_origin(cv["origin"])
    st.caption("Yield and price are synthetic and do not react to weather. A single euro figure is never precise: "
               "the 2016 cost ranges roughly EUR 6k-48k across reasonable assumptions.")
