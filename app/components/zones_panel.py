"""Owner: Mirela (map by Lamia). Field zones expander: pre-rendered PNG, no live satellite call."""
import streamlit as st

import ui
from config import ASSETS_DIR


def render() -> None:
    with st.expander("Field zones (real field example)"):
        png = ASSETS_DIR / "zones.png"
        if png.exists():
            st.image(str(png), caption="Gasawy field, Sentinel-1 VV change 29 Sep - 5 Oct 2016")
        else:
            st.info("app/assets/zones.png not added yet (Lamia's zone map).")
        ui.show_origin("real")
