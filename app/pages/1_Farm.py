"""Farm page (spec 9.1): headline numbers and parcel tiles coloured by the replay day's status (no pseudo-map, F7)."""
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

machine = st.selectbox("Colour the tiles by today's status for", list(prm.MACHINES), index=1,
                       format_func=lambda m: f"{m}: {prm.MACHINES[m]['profile']} (full load)")
if REAL:
    statuses, lc = _status(holding, pd.Timestamp(replay), machine)
    farm = farm.assign(status=farm.parcel_id.map(statuses).fillna("not available"))
    st.caption(f"Status on {pd.Timestamp(replay):%d %b %Y} for class {lc} (field access, replay weather). "
               "Tile size follows area.")

names = {"BARL": "Winter barley", "COWT": "Winter wheat", "RAPE": "Winter rapeseed", "MAIZ": "Maize",
         "SUNF": "Sunflower", "HAY": "Hay", "OLIV": "Olives"}
order = ["BARL", "COWT", "RAPE"] + sorted(set(farm.crop) - {"BARL", "COWT", "RAPE"})
for crop in [c for c in order if c in set(farm.crop)]:
    sub = farm[farm.crop == crop].sort_values("area_ha", ascending=False)
    ha = crops.get(crop, {}).get("ha", round(float(sub.area_ha.sum()), 1))
    st.markdown(f"#### {names.get(crop, crop)} · {len(sub)} parcels · {ha} ha")
    cols = st.columns(6)
    for i, r in enumerate(sub.itertuples()):
        colour = ui.STATUS_COLORS.get(r.status, ui.STATUS_COLORS["not available"])
        h = int(70 + min(r.area_ha, 12) * 6)
        with cols[i % 6]:
            st.markdown(
                f"<div style='border-left:8px solid {colour};background:#fafafa;border-radius:8px;padding:6px 8px;"
                f"margin-bottom:8px;min-height:{h}px'><b style='font-size:0.8rem'>{r.parcel_id[-7:]}</b><br>"
                f"<span style='font-size:0.75rem'>{r.area_ha:.1f} ha · clay {r.clay_pct:.0f}% · sand {r.sand_pct:.0f}%</span><br>"
                f"<span style='color:{colour};font-weight:700;font-size:0.8rem'>{r.status}</span></div>",
                unsafe_allow_html=True)
ui.show_origin("synthetic+modelled", not REAL)
with st.expander("Parcel table"):
    cols = [c for c in ["parcel_id", "crop", "crop_previous", "area_ha", "clay_pct", "sand_pct", "om_pct", "fc_mm",
                        "wp_mm", "status"] if c in farm.columns]
    st.dataframe(farm[cols], hide_index=True, width="stretch")
