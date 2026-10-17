"""Field zones panel (spec 8; map by Lamia): pre-rendered Sentinel-1 zone PNG of a real field, no live API call."""
import streamlit as st

import ui
from config import ASSETS_DIR

ZONES = [("wettest: check first / avoid when wet", 20.8), ("normal", 41.5), ("drier", 20.8)]   # ha, pre-event test


def render() -> None:
    with st.expander("Field zones: where to be careful on a real field (Sentinel-1 radar, Sentinel-2 NDVI)"):
        wet, prod = st.tabs(["Wetness after rain (radar, Oct 2016)", "Productivity (NDVI, 2017-2024)"])
        with wet:
            _radar()
        with prod:
            _ndvi()


def _radar() -> None:
    png = ASSETS_DIR / "zones.png"
    c1, c2 = st.columns([3, 2])
    with c1:
        if png.exists():
            st.image(str(png), width="stretch")
        else:
            st.info("app/assets/zones.png is missing (Lamia's zone map).")
    with c2:
        st.markdown("**Real 80.7 ha field near Poznań** (28 km from the demo region, same weather), "
                    "Sentinel-1 radar, change 29 Sep -> 5 Oct 2016 after 37 mm of rain.")
        for name, ha in ZONES:
            st.markdown(f"- {name}: **{ha} ha**")
        st.caption("The radar saw the field ~5 dB wetter than before the rain, still wet on 11-14 Oct (the demo "
                   "days). Consistent with the model, not proof: radar also responds to roughness and residue. "
                   "In production FieldGo uses the farmer's own field boundaries. Zones show WHERE to be careful, "
                   "never WHETHER to go.")
        ui.show_origin("real", False)
        st.caption("Contains modified Copernicus Sentinel data [2016]. Boundary: GUGiK ULDK.")


def _ndvi() -> None:
    from engine import params as prm
    z = prm.NDVI_ZONES
    png = ASSETS_DIR / "ndvi_zones.png"
    c1, c2 = st.columns([3, 2])
    with c1:
        if png.exists():
            st.image(str(png), width="stretch")
        else:
            st.info("app/assets/ndvi_zones.png is missing.")
    with c2:
        st.markdown("**Same field, Sentinel-2 NDVI in spring of 6 winter-crop years** (2017-2024), each year relative "
                    "to the field median, then the median over years.")
        for name, ha in z["zones_ha"].value.items():
            st.markdown(f"- {name}: **{ha} ha**")
        st.caption(f"The lower zone is about {abs(z['lower_vs_median_pct'].value)}% below the field median, and the "
                   f"pattern repeats moderately from year to year (rank correlation {z['year_to_year_rank_corr'].value}). "
                   "It does not coincide with the wet zones of the radar (correlation ~0): productivity and wetness "
                   "are different layers. Use: where to look for compacted subsoil or poor drainage first, where to "
                   "check emergence after a wet sowing. NDVI does not measure trafficability.")
        ui.show_origin("real", False)
        st.caption("Contains modified Copernicus Sentinel data [2017-2024]. Boundary: GUGiK ULDK.")
