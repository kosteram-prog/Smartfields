"""Cost-of-delay and contractor cards for the Season page (spec 9.2; Mirela's slice, written by Marek's agent)."""
import streamlit as st

import config
import ui
from engine import params as prm

REAL = config.data_dir_or_none() is not None
CROPS = {"BARL": "barley", "COWT": "wheat"}


@st.cache_data(show_spinner="Costing 10 autumns...")
def _costs(params: dict):
    from engine.cost import season_costs
    return season_costs(params)


@st.cache_data
def _economics():
    from engine.cost import default_economics
    return default_economics()


def _inputs() -> dict:
    econ = _economics()
    with st.expander("Cost inputs (expected yield, price, optimal sowing date, contractor price)"):
        st.caption("Loss starts at the end of the optimal sowing window, not at your deadline. "
                   "Yields and prices are synthetic and do not react to weather: enter your own for a real decision.")
        out = {"yield_t_ha": {}, "price_eur_t": {}, "optimum_end": {}}
        for crop, name in CROPS.items():
            c = st.columns(3)
            out["yield_t_ha"][crop] = c[0].number_input(f"Expected {name} yield (t/ha)", 0.0, 20.0,
                                                        float(econ["yield_t_ha"].get(crop, 0.0)), 0.1, key=f"y_{crop}")
            out["price_eur_t"][crop] = c[1].number_input(f"{name.capitalize()} price (EUR/t)", 0.0, 1000.0,
                                                         float(econ["price_eur_t"].get(crop, 0.0)), 5.0, key=f"p_{crop}")
            out["optimum_end"][crop] = c[2].text_input(f"End of optimal {name} sowing (MM-DD)",
                                                       prm.COST["optimum_end"][crop].value, key=f"o_{crop}")
        out["contractor_price"] = st.number_input("Contractor price (EUR/ha)", 0.0, 500.0,
                                                  float(prm.COST["contractor_price_eur_ha"].value), 1.0,
                                                  help=prm.COST["contractor_price_eur_ha"].source)
    return out


def render(schedule=None, parcels=None, params=None) -> None:
    if not REAL:
        from engine import stubs
        c = stubs.season_cost()
        ui.metric("Median cost of delay (weather part)", ui.fmt_eur(c["median"]["weather_default"]), c["origin"], True)
        return
    p = dict(params or {}) | _inputs()
    res = _costs(p)
    cost = res["cost"]
    m, w = cost["median"], cost["worst_year"]
    py = cost["per_year"].set_index("year")
    c1, c2, c3 = st.columns(3)
    with c1:
        ui.metric("Median cost of delay (weather part)", ui.fmt_eur(m["weather_default"]), cost["origin"], False,
                  help="Yield lost because the weather delayed sowing (real schedule minus the same farm in perfect weather)")
        st.caption(f"range {ui.fmt_eur(m['weather_low'])} - {ui.fmt_eur(m['weather_high'])} (loss rate 0.5-1.5 %/day)")
    with c2:
        y = 2016 if 2016 in py.index else w["year"]
        ui.metric(f"Wet autumn {y}", ui.fmt_eur(py.loc[y, "weather_default"]), cost["origin"], False)
        st.caption(f"range {ui.fmt_eur(py.loc[y, 'weather_low'])} - {ui.fmt_eur(py.loc[y, 'weather_high'])}"
                   + (f" · costliest year: {w['year']} ({ui.fmt_eur(w['weather_default'])})" if w["year"] != y else ""))
    with c3:
        ui.metric("Late-start cost (separate line)", ui.fmt_eur(m["late_start_default"]), cost["origin"], False,
                  help="Cost of starting on the window start (after maize) even in perfect weather: a rotation choice")
        st.caption("every year, from the rotation (sowing after maize), not from the weather")
    cv = res.get("contractor_value")
    if cv:
        with st.container(border=True):
            st.markdown(f"**Contractor +{res['contractor_ha_day']:g} ha/day** saves about "
                        f"**{ui.fmt_eur(cv['value_median'])}** in the median year and **{ui.fmt_eur(cv['value_worst'])}** "
                        f"in {cv['worst_year']}.")
            if isinstance(cv.get("net_benefit_worst"), float):
                st.caption(f"Contractor sows ~{cv['contractor_ha_median']:.0f} ha at {ui.fmt_eur(p['contractor_price'])}/ha "
                           f"(~{ui.fmt_eur(cv['contractor_fee_median'])}): net {ui.fmt_eur(cv['net_benefit_median'])} in the "
                           f"median year, {ui.fmt_eur(cv['net_benefit_worst'])} in {cv['worst_year']}.")
            ui.show_origin(cv["origin"], False)
    else:
        st.caption("Set 'Contractor (extra ha/day)' above to see what a contractor is worth.")
    sens = {}
    for wgt in prm.SEASON["caution_weight_options"].value:
        cs = _costs(p | {"caution_weight": float(wgt), "contractor_ha_day": 0.0})["cost"]["per_year"].set_index("year")
        sens[wgt] = cs.loc[2016, "weather_default"] if 2016 in cs.index else None
    if all(isinstance(v, float) for v in sens.values()):
        st.caption(f"Sensitivity, 2016 weather cost: {ui.fmt_eur(sens[0.5])} if a CAUTION day counts as ½ day · "
                   f"{ui.fmt_eur(sens[0.0])} if 0 · {ui.fmt_eur(sens[1.0])} if 1 day.")
    st.caption("Euro values use synthetic yield and price and assumed loss rates: always a range, never a precise "
               "number (the 2016 cost moves by several times across reasonable threshold assumptions).")
