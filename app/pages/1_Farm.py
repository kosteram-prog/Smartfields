"""Farm page (owner: Mirela): headline numbers and parcel tiles (not a map)."""
import streamlit as st

import ui
from engine import stubs  # TODO: engine.data.load_farm

ui.shell("Farm")
fs = stubs.farm_summary(st.session_state["farm"])
c = st.columns(5)
for col, (label, val) in zip(c, [("Parcels", fs["parcels"]), ("UAA (ha)", fs["uaa_ha"]),
                                  ("Winter cereals (ha)", fs["winter_cereals_ha"]),
                                  ("Barley", f"{fs['barley']['parcels']} parcels / {fs['barley']['ha']} ha"),
                                  ("Wheat", f"{fs['wheat']['parcels']} parcels / {fs['wheat']['ha']} ha")]):
    with col:
        ui.metric(label, val, fs["origin"])
st.caption(f"{fs['holding_id']} · {fs['nuts3']} (Poznan region) · {fs['awu']} AWU · not organic")

st.subheader("Winter-cereal parcels (stub shows 6 of 21)")
farm = stubs.load_farm(fs["holding_id"])
cols = st.columns(3)
for i, r in enumerate(farm.itertuples()):
    with cols[i % 3], st.container(border=True):
        st.markdown(f"**{r.parcel_id}**")
        st.write(f"{'Barley' if r.crop == 'BARL' else 'Wheat'} · {r.area_ha} ha")
        st.write(f"Clay {r.clay_pct}% · sand {r.sand_pct}% · OM {r.om_pct}%")
        st.write(f"FC {r.fc_mm} mm · WP {r.wp_mm} mm · priority {r.priority}")
        ui.show_origin("synthetic+modelled")
