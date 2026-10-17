"""FieldGo router. Run from the repo root: streamlit run app/main.py

Renders the shared sidebar once (farm, replay date) and the navigation in sections, then the selected page.
"""
import streamlit as st

import config
import ui

st.set_page_config(page_title="FieldGo", page_icon="🌾", layout="wide")
REAL = config.data_dir_or_none() is not None


@st.cache_resource(show_spinner=False)
def _warm_up() -> bool:
    """B9: fill the engine's process-wide caches (data, soil water, season inputs) in the background, once per server."""
    import threading

    def run():
        try:
            import pandas as pd
            from engine.season import season
            from engine.today import today
            today("PARCEL-0149869", pd.Timestamp(ui.prm.DEMO["replay_date"].value), "M2", 100, 1, "sowing")
            season({})
        except Exception:  # noqa: BLE001  (warm-up is best effort; pages compute on demand anyway)
            pass
    threading.Thread(target=run, daemon=True).start()
    return True


if REAL:
    _warm_up()
ui.sidebar(real=REAL)
P = "views/"
nav = st.navigation({
    "": [st.Page(P + "0_Home.py", title="Home", icon="🏠", default=True)],
    "Decide": [st.Page(P + "3_Today.py", title="Today", icon="🚜"),
               st.Page(P + "2_Season.py", title="Season", icon="📅")],
    "Farm": [st.Page(P + "1_Farm.py", title="Farm map", icon="🗺️"),
             st.Page(P + "4_Records.py", title="Records", icon="📝"),
             st.Page(P + "6_Loss.py", title="Loss calculator", icon="💶")],
    "Data": [st.Page(P + "5_About.py", title="About the data", icon="ℹ️"),
             st.Page(P + "7_Satellite.py", title="Plot zones", icon="🛰️"),
             st.Page(P + "8_Connect.py", title="Connect", icon="🔌")],
})
nav.run()
