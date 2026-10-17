"""Farm page: headline numbers, farm map and today's plan coloured by the replay day's status."""
import pandas as pd
import streamlit as st

import config
import ui
from engine import params as prm

replay = ui.shell("Farm")
REAL = config.data_dir_or_none() is not None
holding = st.session_state["farm"]

if not REAL:
    from engine import stubs
    st.warning("FIELDGO_DATA_DIR is not set: showing stub numbers.")
    fs, farm = stubs.farm_summary(holding), stubs.load_farm(holding)
    farm["status"] = "not available"
else:
    from engine import data, soil, status

    @st.cache_data
    def _farm(h):
        return data.farm_summary(h), data.load_farm(h)

    @st.cache_data(show_spinner="Computing today's status for every parcel...")
    def _status(h, date, machine):
        f = data.load_farm(h)
        sw = soil.soil_water(f, data.load_weather(f.nuts3.iloc[0]))
        sw = sw[sw.date == pd.Timestamp(date)]
        lc, _ = status.axle_load_class(machine, 100)
        st_ = status.status_table(sw, f, lc)
        return dict(zip(st_.parcel_id, st_.status)), lc

    fs, farm = _farm(holding)

c = st.columns(5)
crops = fs.get("crops") or {}
barl, cowt = crops.get("BARL", fs.get("barley", {})), crops.get("COWT", fs.get("wheat", {}))
for col, (label, val) in zip(c, [("Parcels", fs["parcels"]), ("UAA (ha)", fs["uaa_ha"]),
                                  ("Winter cereals (ha)", fs["winter_cereals_ha"]),
                                  ("Barley", f"{barl.get('parcels', '-')} / {barl.get('ha', '-')} ha"),
                                  ("Wheat", f"{cowt.get('parcels', '-')} / {cowt.get('ha', '-')} ha")]):
    with col:
        ui.metric(label, val, fs["origin"], not REAL)
awu = fs.get("awu")
st.caption(f"{fs['holding_id']} · {fs['nuts3']} (Wielkopolska, Poznań region) · "
           f"{awu if isinstance(awu, str) else f'{awu} AWU'} · {'organic' if fs.get('organic') else 'not organic'} · "
           "synthetic farm from the organisers' dataset")

machine = ui.pick(st, "selectbox", "Machine for today's status", "machine", list(prm.MACHINES),
                       format_func=lambda m: f"{m}: {prm.MACHINES[m]['profile']} (full load)")
if REAL:
    statuses, lc = _status(holding, pd.Timestamp(replay), machine)
    farm = farm.assign(status=farm.parcel_id.map(statuses).fillna("not available"))
    st.caption(f"Status on {pd.Timestamp(replay):%d %b %Y} for {prm.MACHINES[machine]['profile'].lower()} "
               f"(class {lc}, replay weather).")

# ------------------------------------------------------------------ A2: map of the farm coloured by status
if REAL:
    from components import farm_map
    lbl = {r.parcel_id: ui.parcel_label(r.parcel_id, r.crop, r.area_ha, r.clay_pct, r.sand_pct) for r in farm.itertuples()}
    fig = farm_map.figure(farm, height=560, labels=lbl)
    if fig is not None:
        st.markdown("#### Farm map: who can go where today")
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        st.caption("Illustrative layout of 30 of the farm's fields (the organisers' parcel shapes are placeholders). "
                   "Field sizes on the map are illustrative; crop, real area, soil and status on hover come from the "
                   "data and the engine. In production: the farmer's own IACS field boundaries.")

# ------------------------------------------------------------------ A1: today's plan for the whole farm
if REAL:
    from engine import season
    st.markdown("#### Today's plan")
    op = st.radio("Operation", ["sowing (winter cereals)", "all fields"], horizontal=True, key="farm_plan_op")
    pool = farm[farm.crop.isin(season.autumn_crops())] if op.startswith("sowing") else farm
    pr = season.priority(pool)[["parcel_id", "priority", "rank"]] if op.startswith("sowing") else \
        pool[["parcel_id"]].assign(priority=0, rank=range(1, len(pool) + 1))
    plan = pool.merge(pr, on="parcel_id")
    rank = {"GO": 0, "CAUTION": 1, "NO-GO": 2}
    plan = plan.assign(_s=plan.status.map(rank).fillna(3)).sort_values(["_s", "rank"])
    m = prm.MACHINES[machine]
    cap = m["rate_ha_h"].value * prm.CAPACITY["hours_per_day"].value * prm.CAPACITY["own_units"].value
    go_ha = plan.loc[plan.status == "GO", "area_ha"]
    cum = go_ha.cumsum()
    plan["today"] = ""
    plan.loc[cum.index, "today"] = ["✅ today" if c - a < cap else "next GO day" for c, a in zip(cum, go_ha)]
    k = st.columns(4)
    for col, s_ in zip(k[:3], ["GO", "CAUTION", "NO-GO"]):
        col.metric(f"{s_} area", f"{plan.loc[plan.status == s_, 'area_ha'].sum():.0f} ha")
        col.caption(f"{(plan.status == s_).sum()} fields")
    k[3].metric(f"Doable today with 1 × {machine}", f"{min(cap, go_ha.sum()):.0f} ha")
    k[3].caption(f"capacity {cap:.0f} ha/day ({m['rate_ha_h'].value} ha/h × {prm.CAPACITY['hours_per_day'].value} h)")
    show = plan.assign(field=plan.parcel_id.map(ui.field_name), crop_=plan.crop.map(lambda c: ui.CROP_WORDS.get(c, c)),
                       soil=[ui.soil_word(c, s_) for c, s_ in zip(plan.clay_pct, plan.sand_pct)])
    st.dataframe(show[["field", "crop_", "area_ha", "soil", "status", "today", "parcel_id"]], hide_index=True,
                 width="stretch", height=320,
                 column_config={"crop_": "crop", "area_ha": st.column_config.NumberColumn("Area (ha)", format="%.1f"),
                                "today": "plan"})
    by_machine = []
    for mid in ("M1", "M2", "M3", "M5"):
        sts, _ = _status(holding, pd.Timestamp(replay), mid)
        ha = pool.assign(s=pool.parcel_id.map(sts)).query("s == 'GO'").area_ha.sum()
        by_machine.append(f"{mid} {prm.MACHINES[mid]['profile'].split(',')[0].lower()}: **{ha:.0f} ha GO**")
    st.markdown("Same day, other machines: " + " · ".join(by_machine))
    ui.show_origin("real+modelled+synthetic", False)

with st.expander("Field tiles by crop"):
    names = {"BARL": "Winter barley", "COWT": "Winter wheat", "RAPE": "Winter rapeseed", "MAIZ": "Maize",
             "SUNF": "Sunflower", "HAY": "Hay", "OLIV": "Olives"}
    order = ["BARL", "COWT", "RAPE"] + sorted(set(farm.crop) - {"BARL", "COWT", "RAPE"})
    for crop in [c for c in order if c in set(farm.crop)]:
        sub = farm[farm.crop == crop].sort_values("area_ha", ascending=False)
        ha = crops.get(crop, {}).get("ha", round(float(sub.area_ha.sum()), 1))
        st.markdown(f"##### {names.get(crop, crop)} · {len(sub)} fields · {ha} ha")
        cols = st.columns(6)
        for i, r in enumerate(sub.itertuples()):
            colour = ui.STATUS_COLORS.get(r.status, ui.STATUS_COLORS["not available"])
            h = int(70 + min(r.area_ha, 12) * 6)
            with cols[i % 6]:
                st.markdown(
                    f"<div style='border-left:8px solid {colour};background:#fafafa;border-radius:8px;padding:6px 8px;"
                    f"margin-bottom:8px;min-height:{h}px'><b style='font-size:0.85rem'>{ui.field_name(r.parcel_id)}</b><br>"
                    f"<span style='font-size:0.75rem'>{r.area_ha:.1f} ha · {ui.soil_word(r.clay_pct, r.sand_pct)}</span><br>"
                    f"<span style='color:{colour};font-weight:700;font-size:0.8rem'>{r.status}</span></div>",
                    unsafe_allow_html=True)
    ui.show_origin("synthetic+modelled", not REAL)
with st.expander("Parcel table"):
    cols = [c for c in ["parcel_id", "crop", "crop_previous", "area_ha", "clay_pct", "sand_pct", "om_pct", "fc_mm",
                        "wp_mm", "status"] if c in farm.columns]
    st.dataframe(farm[cols], hide_index=True, width="stretch")
