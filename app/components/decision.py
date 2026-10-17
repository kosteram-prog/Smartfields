"""Go now or wait? Both in euro for the plot on the Today page, with live tyre pressure and trafficked share.

go now : engine.cost.go_now_cost (axle load x tyres x how wet the soil is; subsoil from the compaction check)
wait   : engine.cost.wait_cost (season cost of delay with this day skipped, whole-farm sowing queue, replay year)
"""
import streamlit as st

import config
import ui
from engine import params as prm

REAL = config.data_dir_or_none() is not None
VERDICT = {"go": ("GO", "Going now costs less than leaving it for later"),
           "wait": ("NO-GO", "Leaving it for a drier day costs less than the damage"),
           "close": ("CAUTION", "About the same: go only on the driest part, or do another plot first")}


@st.cache_data(show_spinner=False)
def _wait(date, params):
    if not REAL:
        from engine import stubs
        return stubs.wait_cost(date, dict(params))
    from engine.cost import wait_cost
    return wait_cost(date, dict(params))


@st.cache_data(show_spinner=False)
def _go_ha(holding, date, machine, load, operation, exclude):
    """Area of the other plots that are GO today for this machine (same pool as the season: autumn crops)."""
    import pandas as pd
    from engine import season, status
    if REAL:
        from engine import data, soil
        farm = data.load_farm(holding)
        pool = farm[farm.crop.isin(season.autumn_crops())] if operation == "sowing" else farm
        sw = soil.soil_water(pool, data.load_weather(pool.nuts3.iloc[0]))
    else:
        from engine import stubs
        farm = stubs.load_farm(holding)
        pool = farm[farm.crop.isin(season.autumn_crops())] if operation == "sowing" else farm
        sw = stubs.soil_water(pool)
    lc, _ = status.axle_load_class(machine, load)
    st_ = status.status_table(sw[sw.date == pd.Timestamp(date)], pool, lc, 1, operation)
    go = st_[(st_.status == "GO") & (st_.parcel_id != exclude)].parcel_id
    return float(pool[pool.parcel_id.isin(go)].area_ha.sum())


def _tile(title, big, sub, colour="#f4f5f7", ink="#1f2328"):
    st.markdown(f"<div style='background:{colour};border-radius:12px;padding:12px 14px;height:100%'>"
                f"<div style='font-size:0.82rem;opacity:0.8'>{title}</div>"
                f"<div style='font-size:1.6rem;font-weight:700;color:{ink}'>{big}</div>"
                f"<div style='font-size:0.8rem;opacity:0.85'>{sub}</div></div>", unsafe_allow_html=True)


def render(t: dict, when, machine: str, load: int, passes: int, tyre_bar=None) -> None:
    if t.get("status") not in ("GO", "CAUTION", "NO-GO"):
        return
    from engine.cost import go_now_cost, go_or_wait
    soil, cond = t.get("soil") or {}, t.get("conditions") or {}
    m = prm.GO_NOW_MODEL
    with st.container(border=True):
        st.markdown("#### Go now or wait?")
        c1, c2, c3 = st.columns(3)
        default_bar = float(tyre_bar or m["default_tyre_bar"].value.get(t["load_class"], 1.4))
        bar = c1.slider("Tyre pressure (bar)", 0.6, 3.0, default_bar, 0.1, key=f"dec_bar_{t['load_class']}_{tyre_bar}",
                        help="Lower pressure = bigger footprint = less stress in the topsoil. Default: typical for "
                             "this axle load.")
        share = c2.slider("Share of the plot under the wheels (%)", 10, 100,
                          int(prm.WET_TRAFFIC_LOSS["trafficked_share"].value * 100), 5, key="dec_share",
                          help="Lower with tramlines / controlled traffic, higher with headland turning.") / 100
        price_adj = c3.slider("Grain price vs default (%)", 50, 150, 100, 10, key="dec_price",
                              help="Default: synthetic Jul-Aug price of the farm data")
        from engine.cost import default_economics
        econ = default_economics()
        econ = {"yield_t_ha": econ["yield_t_ha"],
                "price_eur_t": {k: v * price_adj / 100 for k, v in econ["price_eur_t"].items()},
                "trafficked_share": share}
        g = go_now_cost(t["status"], cond.get("rwc_eff"), t.get("axle_load_t"), t["load_class"], soil.get("clay_pct"),
                        soil.get("sand_pct"), soil.get("om_pct"), t.get("crop"), t.get("area_ha"), bar, passes, econ)
        sowing = t.get("operation") == "sowing"
        w = _wait(when, tuple(sorted({"parcel_id": t["parcel_id"], "machine_id": machine, "load_pct": load,
                                      "passes": passes}.items()))) if sowing else {"eur": "not available"}
        if isinstance(w.get("eur"), (int, float)) and price_adj != 100:
            w = w | {"eur": round(w["eur"] * price_adj / 100, 0)}
        cap = prm.MACHINES[machine]["rate_ha_h"].value * prm.CAPACITY["hours_per_day"].value
        frac = min(1.0, float(t.get("area_ha") or 0) / cap) if cap else 1.0
        w_part = w | ({"eur": round(w["eur"] * frac, 0)} if isinstance(w.get("eur"), (int, float)) else {})
        v = go_or_wait(g, w_part)
        other_go = _go_ha(st.session_state.get("farm"), when, machine, load, t.get("operation"), t["parcel_id"]) \
            if t["status"] != "GO" else 0.0
        if t["status"] != "GO" and other_go >= cap:
            v = v | {"verdict": "other"}
        a, b, c = st.columns(3)
        with a:
            py = g.get("persistent_eur_per_year")
            _tile(f"Go now on {ui.field_name(t['parcel_id'])}", ui.fmt_eur(g["eur"]),
                  f"year 1 · {g['loss_pct']:g}% loss on {g.get('trafficked_ha', '?')} ha under the wheels"
                  + (f"<br>+ {ui.fmt_eur(py)}/yr for ~{g['persistent_years']} yrs from the subsoil"
                     if isinstance(py, (int, float)) and py > 0 else "<br>no lasting subsoil damage expected"))
        with b:
            if sowing and isinstance(w.get("eur"), (int, float)):
                _tile("Leave this plot for later", ui.fmt_eur(w_part["eur"]),
                      f"its share ({frac:.0%}) of one lost working day: a whole day costs {ui.fmt_eur(w['eur'])} "
                      "in later sowing of the farm (season model, this autumn)")
            else:
                _tile("Wait one day", "not modelled", w.get("message") or "Waiting cost is modelled for autumn "
                      "sowing only.")
        with c:
            if v["verdict"] == "other":
                colour = ui.STATUS_COLORS["GO"]
                _tile("Cheaper option", "Do a GO plot first",
                      f"{other_go:.0f} ha of other plots are GO today, more than the machine does in a day "
                      f"(~{cap:.0f} ha): no reason to drive on this wet plot. See the safer plan below.",
                      colour=colour + "22", ink=colour)
            elif v["verdict"] in VERDICT:
                col_as, text = VERDICT[v["verdict"]]
                colour = ui.STATUS_COLORS[col_as]
                _tile("Cheaper option", {"go": "Go now", "wait": "Wait", "close": "Close call"}[v["verdict"]],
                      f"{text}.<br>Go: {ui.fmt_eur(v['go_total'])} incl. subsoil years · later: {ui.fmt_eur(v['wait'])}",
                      colour=colour + "22", ink=colour)
            else:
                _tile("Cheaper option", "—", "Needs both numbers.")
        d = g.get("drivers") or {}
        if t["status"] != "GO":
            st.caption(f"What drives the go-now number: soil wetter than the GO limit by "
                       f"{max(0.0, (cond.get('rwc_eff') or 0) - d.get('go_limit_rwc', 0)):.2f} RWC (wetness factor "
                       f"{d.get('wetness', 0):.2f}) · axle {t.get('axle_load_t')} t (factor {d.get('axle', 0):.2f}) · "
                       f"tyres {bar:.1f} bar (factor {d.get('tyre', 0):.2f}) · subsoil overstress factor "
                       f"{d.get('subsoil', 0):.2f}. Try a lower tyre pressure or a lighter load and watch it change.")
        else:
            st.caption("GO: the soil carries this load today, so no wet-traffic loss is counted.")
        with st.popover("How is this calculated?"):
            st.markdown(
                "- **Go now, year 1** = 15 % (Håkansson: 10-12 t axles on wet soil) × axle load / 11 t × "
                "(tyre bar / 2.0)^0.5 × wetness, on the trafficked share of the plot × expected yield × price. "
                "Wetness rises from 0 at the GO limit of this load class to 1 at RWC 1.10.\n"
                "- **Subsoil** = 6 %/yr (RECARE 2018) × subsoil overstress from the compaction check (stress vs "
                "strength at 30-80 cm, today's wetness) relative to an 11 t / 2 bar / wet clay-loam anchor, ~10 years.\n"
                "- **A lost day** = the whole farm's sowing-delay cost this autumn with today skipped (barley "
                "0.43 %/day, wheat 1 %/day after the optimum date).\n"
                "- **Leave it for later** = the plot's share of one working day (area / machine capacity per day) × the cost of "
                "losing a whole day.\n"
                "- Verdict: go if go-now (incl. subsoil years, undiscounted) < 0.8 × that; wait if > 1.25 ×.\n"
                "Illustrative values: calibrate in pilots.")
        ui.show_origin("modelled+synthetic+assumption", False)
