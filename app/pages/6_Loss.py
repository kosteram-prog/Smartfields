"""Loss calculator (Mirela's page, rebuilt on the engine 16 Oct): what does entering wet cost vs waiting?

Every number comes from the same engine as Season and Today:
  entering now  -> engine.cost.entry_cost (spec 6.8.3, status x axle-load class, illustrative)
  waiting a day -> engine.cost.wait_cost  (season_cost with the day skipped, replay year)
"""
import pandas as pd
import streamlit as st

import config
import ui
from engine import params as prm

replay = ui.shell("Loss calculator")
st.caption("Go now on wet soil, or wait? Both answers in euro, from the same engine as the Season and Today pages. "
           "Euro values are illustrative: synthetic yield and price, compaction losses from one published anchor.")
if config.data_dir_or_none() is None:
    st.warning("FIELDGO_DATA_DIR is not set: the loss calculator needs the data extracts.")
    st.stop()

from engine import data, season, soil, status  # noqa: E402
from engine.cost import default_economics, entry_cost, wait_cost  # noqa: E402

c = st.columns(4)
machine = c[0].selectbox("Machine", list(prm.MACHINES), index=2, format_func=lambda m: f"{m}: {prm.MACHINES[m]['profile']}")
load = c[1].slider("Load (%)", 0, 100, 100)
operation = c[2].selectbox("Operation", ["sowing", "fertilising", "spraying"])
share = c[3].slider("Trafficked share of each parcel (%)", 10, 100,
                    int(prm.WET_TRAFFIC_LOSS["trafficked_share"].value * 100),
                    help="Share of the field driven over by the wheels (lower with tramlines). Spec 6.8.3")


@st.cache_data(show_spinner="Status of every parcel...")
def table(holding, date, machine, load, operation, share):
    farm = data.load_farm(holding)
    pool = farm[farm.crop.isin(season.autumn_crops())] if operation == "sowing" else farm
    sw = soil.soil_water(pool, data.load_weather(pool.nuts3.iloc[0]))
    sw = sw[sw.date == pd.Timestamp(date)]
    lc, axle = status.axle_load_class(machine, load)
    stt = status.status_table(sw, pool, lc, 1, operation).set_index("parcel_id")
    econ = default_economics(holding)
    rows = []
    for r in pool.itertuples():
        s_ = stt.status.get(r.parcel_id, "not available")
        e = entry_cost(s_, lc, r.crop, r.area_ha, {"trafficked_share": share / 100.0, **econ})
        rows.append({"parcel_id": r.parcel_id, "crop": r.crop, "area_ha": r.area_ha, "clay_pct": r.clay_pct,
                     "status": s_, "go_now_eur": e["eur"]})
    return pd.DataFrame(rows), lc, axle


t, lc, axle = table(st.session_state["farm"], pd.Timestamp(replay), machine, load, operation, share)
num = pd.to_numeric(t.go_now_eur, errors="coerce")
wet = t[t.status.isin(["CAUTION", "NO-GO"])]
st.caption(f"{pd.Timestamp(replay):%d %b %Y} · {machine} at {load}% -> axle {axle} t, class {lc}")

k = st.columns(3)
with k[0]:
    ui.metric("Go now on every CAUTION / NO-GO parcel", ui.fmt_eur(float(num[wet.index].sum())), "synthetic+assumption",
              False, help="Year-1 yield loss on the trafficked area (spec 6.8.3); part of it can last for years")
    st.caption(f"{len(wet)} parcels, {wet.area_ha.sum():.0f} ha")
with k[1]:
    go = t[t.status == "GO"]
    ui.metric("Go only where GO", ui.fmt_eur(0.0), "modelled", False)
    st.caption(f"{len(go)} parcels, {go.area_ha.sum():.0f} ha workable today")
with k[2]:
    if operation == "sowing":
        w = wait_cost(pd.Timestamp(replay), {"machine_id": machine})
        ui.metric("Wait one day (whole farm)", ui.fmt_eur(w["eur"]), w["origin"], False,
                  help="Season cost of delay with this day skipped minus with it used (replay year)")
        st.caption(w.get("message") or (f"range {ui.fmt_eur(w['eur_low'])} - {ui.fmt_eur(w['eur_high'])}"
                                        if isinstance(w.get("eur_low"), float) else ""))
    else:
        st.metric("Wait one day", "not available")
        st.caption("Waiting cost is modelled for autumn sowing only.")

st.subheader("Per parcel")
st.dataframe(t.sort_values(["status", "go_now_eur"], ascending=[False, False]), hide_index=True, width="stretch",
             column_config={"go_now_eur": st.column_config.NumberColumn("If you go now (EUR, illustrative)", format="%.0f"),
                            "area_ha": st.column_config.NumberColumn("Area (ha)", format="%.1f"),
                            "clay_pct": st.column_config.NumberColumn("Clay %", format="%.0f")})
ui.show_origin("real+modelled+synthetic+assumption", False)
with st.expander("Method and assumptions"):
    st.markdown(f"""
- **Status** per parcel: soil-water model + thresholds by axle-load class (spec 6.4) for this machine and load.
- **If you go now** = loss % x trafficked share x area x expected yield x price. Loss % (year 1) by status and class:
  NO-GO L3 5 %, L4 10 %, L5 15 %; CAUTION half of that; L1-L2 not counted. Anchor: Håkansson multi-site study
  (10-12 t axle load ~15 % year-1 loss; 3-5 % subsoil losses for 12 years); L3/L4 values are interpolated.
- **Wait one day** = season cost of delay (loss 1 %/day after the optimal sowing date, IUNG) with the day skipped.
- Yield and price: synthetic farm data (mean 2017-2024; Jul-Aug price). They do not react to weather.
""")
