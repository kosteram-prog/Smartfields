"""About page (owner: Mirela): method, data origins and the editable parameter tables."""
import pandas as pd
import streamlit as st

import ui
from engine import params as prm

ui.shell("About")
st.markdown("""
FieldGo is a deterministic decision aid for arable farmers. The decision core (GO / CAUTION / NO-GO and every number)
is plain code; no language model decides anything.

- **Season:** 10 historical autumns (AgERA5 2015-2024) replayed against your machine capacity.
- **Today:** a soil-water bucket (0-30 cm) plus machine axle-load class gives a status; replay mode uses history as the forecast.
- **Records:** every 'mark as done' stores the conditions; a checker groups errors into root causes.
""")
st.subheader("Data origins")
st.table(pd.DataFrame({"origin": list(prm.ORIGINS), "meaning": list(prm.ORIGINS.values())}))
st.subheader("Parameters (all are prototype assumptions, to be reviewed by the Product Leads)")
st.markdown("**Machines (spec 6.1)**")
st.dataframe(pd.DataFrame([{"id": k, "profile": v["profile"], "max axle (t)": v["max_axle_t"].value,
                            "load class": v["load_class"], "ha/h": v["rate_ha_h"].value} for k, v in prm.MACHINES.items()]),
             hide_index=True)
st.markdown("**Trafficability thresholds on RWC (spec 6.4)**")
st.dataframe(pd.DataFrame([{"class": k, "GO if <=": v["go"].value, "CAUTION if <=": v["caution"].value}
                           for k, v in prm.THRESHOLDS.items()]), hide_index=True)
ui.show_origin("assumption", stub=False)
st.caption("Synthetic data caveat: yields and prices in the organisers' dataset do not react to weather; weather is real. "
           "Regional weather, not field-level.")
