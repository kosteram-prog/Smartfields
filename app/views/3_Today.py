"""Today page: status, next days and why on top; money side by side; safer plan when not GO; details on demand."""
import pandas as pd
import streamlit as st

import config
import ui
from components import compaction_panel, go_now_line, mark_done, money_line, plan_card
from engine import params as prm

replay = ui.shell("Today")
REAL = config.data_dir_or_none() is not None
if REAL:
    from engine import data
    from engine.today import today as run_today

    @st.cache_data
    def parcels(holding):
        f = data.load_farm(holding)
        f["autumn"] = f.crop.isin(["BARL", "COWT", "RAPE"])
        return f.sort_values(["autumn", "clay_pct"], ascending=[False, False])
else:
    from engine import stubs
    from engine.stubs import today as run_today
    st.warning("FIELDGO_DATA_DIR is not set: showing stub numbers.")

    def parcels(holding):
        return stubs.load_farm(holding)


@st.cache_data
def assess(parcel, date, machine, load, passes, operation, observation, custom, tyre_bar=None, subsoil_bd=None):
    kw = {"observation": observation, "custom_machine": custom,
          "tyre": {"inflation_bar": tyre_bar, "subsoil_bd": subsoil_bd} if tyre_bar else None} if REAL else {}
    return run_today(parcel, date, machine, load, passes, operation, **kw)


farm = parcels(st.session_state["farm"])
label = {r.parcel_id: ui.parcel_label(r.parcel_id, r.crop, r.area_ha, r.clay_pct, r.sand_pct) for r in farm.itertuples()}
c = st.columns([3, 1.4, 2.4, 1.6, 1])
parcel = ui.pick(c[0], "selectbox", "Plot", "parcel", list(farm.parcel_id), format_func=label.get)
operation = ui.pick(c[1], "selectbox", "Operation", "operation", ["sowing", "fertilising", "spraying"])
machine = ui.pick(c[2], "selectbox", "Machine", "machine", list(prm.MACHINES),
                         format_func=lambda m: f"{m}: {prm.MACHINES[m]['profile']}")
load = ui.pick(c[3], "slider", "Load (%)", "load", min_value=0, max_value=100)
passes = c[4].number_input("Passes", 1, int(prm.PASSES["max_passes"].value), 1)
c2 = st.columns([3, 1.4, 1.6])
observation = c2[0].text_input("Your observation (optional)", placeholder="e.g. ball test: soil crumbles / soil ribbons",
                               help="A hand test on the wettest spot raises confidence")
custom = None
with c2[1].popover("Use my own machine"):
    use_custom = st.checkbox("Use my machine instead of the profile", key="use_custom")
    cm_name = st.text_input("Name", "My tractor + drill", key="cm_name")
    cm_axle = st.number_input("Max axle load at this load (t)", 0.5, 20.0, 6.0, 0.5, key="cm_axle",
                              help="Heaviest axle with the current load (weighbridge or manufacturer data)")
    if use_custom:
        custom = {"name": cm_name, "axle_t": float(cm_axle)}
tyre_bar = None
with c2[2].popover("My tyre pressure (optional)"):
    use_tyre = st.checkbox("Check compaction with my tyre pressure", key="use_tyre",
                           help="Without it FieldGo uses the default table (status x axle load). With it: stress in "
                                "the soil vs soil strength today, Terranimo-style.")
    bar = st.number_input("Inflation pressure (bar)", 0.4, 4.0, 1.6, 0.1, key="tyre_bar",
                          help="Field pressure of the heaviest axle's tyres. Wheel load = axle load / 2.")
    bd = st.number_input("Subsoil bulk density 30-60 cm (g/cm³, optional)", min_value=1.0, max_value=2.0, value=None,
                         step=0.05, key="subsoil_bd", placeholder="unknown",
                         help="From a soil core or SoilGrids (30-60 cm). Dense glacial subsoils are often 1.6-1.8. "
                              "Without it FieldGo uses a precautionary default strength.")
    if use_tyre:
        tyre_bar = float(bar)

t = assess(parcel, pd.Timestamp(replay), machine, load, int(passes), operation, observation or None, custom,
           tyre_bar, float(bd) if (tyre_bar and bd) else None)
stub = not REAL
when = pd.Timestamp(replay)

# ------------------------------------------------------------------ row 1: status · next days · why
c_status, c_next, c_why = st.columns([1.1, 1.5, 1.7])
with c_status:
    ui.status_tile(f"{ui.field_name(parcel)} · {when:%d %b %Y}", t["status"], size="3rem")
    a, s = st.columns(2)
    with a:
        ui.status_tile("Plot access", t["access"], size="0.95rem")
    with s:
        ui.status_tile("Operation", t["suitability"], size="0.95rem")
    prof = custom["name"] if custom else prm.MACHINES[machine]["profile"]
    st.caption(f"{prof} at {load}% load: {t.get('axle_load_t')} t on the heaviest axle "
               + ("(your machine data)" if custom else "(typical machine, assumption)"))
    ui.show_origin(t["origin"], stub)
with c_next:
    st.markdown("**Next 72 hours**")
    cols = st.columns(3)
    for col, d in zip(cols, t["strip72"]):
        with col:
            ui.status_tile(pd.Timestamp(d["date"]).strftime("%a %d"), d["status"], size="0.95rem")
    first = t.get("days_to_first_go")
    if first is not None:
        st.caption("First GO: " + ("today" if first == 0 else f"in {first} day(s)" if isinstance(first, int) else str(first)))
    out7 = t.get("outlook7") or []
    if len(out7) > 3:
        chips = "".join(
            f"<span style='display:inline-block;background:{ui.STATUS_COLORS.get(o['status'], ui.STATUS_COLORS['not available'])};"
            f"color:white;border-radius:8px;padding:3px 8px;margin:2px;font-size:0.75rem'>"
            f"{pd.Timestamp(o['date']):%a %d}: {o['status']}</span>" for o in out7)
        st.markdown(f"<div><small>Next 7 days:</small> {chips}</div>", unsafe_allow_html=True)
    st.caption("Replay: the weather that followed this day plays the forecast.")
with c_why:
    st.markdown("**Why**")
    for r in ui.plain_reasons(t):
        st.markdown(r)
    conf = t["confidence"]
    st.markdown(f"<small>Data quality: <b>{t.get('data_quality', 'medium')}</b> · Confidence: <b>"
                f"{conf if isinstance(conf, str) else f'{conf}%'}</b></small>", unsafe_allow_html=True)
    st.markdown(f"**Best next check:** {t['best_next_check']}")

# ------------------------------------------------------------------ row 2: the money, side by side
m_go, m_wait = st.columns(2)
with m_go, st.container(border=True):
    go_now_line.render(t)
with m_wait, st.container(border=True):
    if operation == "sowing":
        money_line.render(when, {"parcel_id": parcel, "machine_id": machine, "load_pct": load, "passes": int(passes)})
    elif operation == "fertilising":
        n_rate = st.number_input("N in this application (kg N/ha)", min_value=0.0, value=None, step=10.0,
                                 placeholder="enter the N rate")
        if not REAL:
            st.caption("N check needs FIELDGO_DATA_DIR (real weather).")
        elif n_rate is None:
            st.caption("Enter the N rate to see the N-loss risk.")
        else:
            from engine.ncheck import n_check
            nc = n_check(when, n_rate, data.load_weather(prm.DEMO["nuts3"].value))
            colour = {"high": "NO-GO", "prohibited": "NO-GO", "medium": "CAUTION", "low": "GO"}.get(nc["risk"], "not available")
            ui.status_tile("N loss risk (prototype)", nc["risk"].upper(), size="1.4rem", color_as=colour)
            st.write(nc["reason"])
            if isinstance(nc["n_at_risk_kg_ha"], tuple):
                lo, hi = nc["n_at_risk_kg_ha"]
                st.markdown(f"Indicative N at risk: **{lo:.0f}-{hi:.0f} kg N/ha** (range, prototype)")
            ui.show_origin(nc["origin"], False)
    else:
        st.caption("Waiting cost is modelled for autumn sowing only.")

# ------------------------------------------------------------------ row 3: safer plan (shown at once when not GO)
if t["status"] in ("CAUTION", "NO-GO"):
    st.markdown("#### Safer plan for today")
    plan_card.render(parcel, replay, machine, load, int(passes), operation)
elif st.button("Find a safer plan", type="primary"):
    plan_card.render(parcel, replay, machine, load, int(passes), operation)

compaction_panel.render(t)
mark_done.render(t, parcel, operation)

# ------------------------------------------------------------------ details on demand
cond = t.get("conditions") or {}
with st.expander("Technical details (soil water, thresholds, weather, data used)"):
    for r in t["reasons"]:
        st.markdown(f"- {r}")
    if cond:
        st.caption(f"Soil RWC_eff {cond['rwc_eff']:.2f} (modelled; 1 = field capacity) · rain today "
                   f"{cond['precip_mm']:.1f} mm, last 48 h {cond['precip_last48h_mm']:.1f} mm · Tmax "
                   f"{cond['tmax_c']:.1f} °C · wind {cond['wind_m_s']:.1f} m/s (real, regional)")
    st.caption("Based on: " + "; ".join(t["based_on"]))
    st.caption("Missing: " + "; ".join(t["missing"]))
if REAL and t["status"] in ("GO", "CAUTION", "NO-GO"):
    with st.expander("Explain in plain words"):
        from engine import explain
        st.write(explain.template(t))
        st.caption("Template explanation (deterministic).")
        import os
        if os.environ.get("ANTHROPIC_API_KEY"):
            if st.button("Rewrite with AI"):
                r = explain.ai_rewrite(t)
                st.info(r["text"])
                st.caption(r["label"] + (f" · {r['note']}" if r["note"] else ""))
        else:
            st.caption("Optional: set ANTHROPIC_API_KEY to let an AI rewrite this text. It receives only these values "
                       "and cannot change them or the decision (checked in code).")
try:
    st.page_link("views/7_Satellite.py", label="Plot zones: where to be careful inside a plot", icon="🛰️")
except Exception:  # noqa: BLE001  (page run on its own, without the router)
    pass
