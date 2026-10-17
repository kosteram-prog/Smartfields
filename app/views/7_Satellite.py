"""Plot zones: the farm on the orthophoto coloured by a satellite layer; click a plot to see its zones inside."""
from __future__ import annotations

import pandas as pd
import streamlit as st

import config
import ui
from components import farm_map, plot_zones, zones_panel
from engine import params as prm

replay = ui.shell("Plot zones")
REAL = config.data_dir_or_none() is not None
st.caption("Inside one plot the soil is not the same. Two free Copernicus layers show where to look first: where the "
           "soil stays wet after rain, and where the crop grows worse year after year. They show **where** inside a "
           "plot to be careful, never **whether** to go: that is the day status on Today.")

lay, zd = farm_map.layout(), plot_zones.data()
if lay is None or zd is None:
    st.info("Zone data not found (app/assets/plot_zones.*). Run tools/make_plot_zones.py.")
    st.stop()

if REAL:
    from engine import data, soil, status

    @st.cache_data(show_spinner=False)
    def _farm(h):
        return data.load_farm(h)

    @st.cache_data(show_spinner="Status of every plot...")
    def _status(h, date, machine):
        f = data.load_farm(h)
        sw = soil.soil_water(f, data.load_weather(f.nuts3.iloc[0]))
        lc, _ = status.axle_load_class(machine, 100)
        t = status.status_table(sw[sw.date == pd.Timestamp(date)], f, lc)
        return dict(zip(t.parcel_id, t.status))
else:
    from engine import stubs

    def _farm(h):
        return stubs.load_farm(h)

    def _status(h, date, machine):
        return {}

farm = _farm(st.session_state["farm"])
ids = [f["parcel_id"] for f in lay["fields"] if f["parcel_id"] in set(farm.parcel_id)]
info = farm.set_index("parcel_id")
labels = {p: ui.parcel_label(p, info.at[p, "crop"], info.at[p, "area_ha"], info.at[p, "clay_pct"], info.at[p, "sand_pct"])
          for p in ids}
if st.session_state.get("parcel") not in ids:
    st.session_state["parcel"] = ids[0]

layer = st.segmented_control("Layer", ["wet", "prod"], default="wet", key="zone_layer", label_visibility="collapsed",
                             format_func=lambda k: ("💧 " if k == "wet" else "🌾 ") + plot_zones.LAYERS[k]["title"])
layer = layer or "wet"
L = plot_zones.LAYERS[layer]

# ------------------------------------------------------------------ the farm: pick a plot
st.markdown(f"**The farm** · {L['sub']}. " + ("Darker blue = wetter after the rain." if layer == "wet" else
            "Darker brown = bigger gap between the weak and the strong part of the plot.") + " Click a plot number.")
fig = plot_zones.overview_figure(farm, layer, st.session_state["parcel"], labels, height=600)
ev = st.plotly_chart(fig, width="stretch", on_select="rerun", selection_mode=("points",),
                     key=f"zones_map_{st.session_state['parcel']}_{layer}", config={"displayModeBar": False})
pts = ev.get("selection", {}).get("points", []) if isinstance(ev, dict) else getattr(
    getattr(ev, "selection", None), "points", [])
if pts:
    clicked = pts[0].get("customdata")
    clicked = clicked[0] if isinstance(clicked, list) else clicked
    if clicked in ids and clicked != st.session_state["parcel"]:
        st.session_state["parcel"] = clicked
        st.rerun()

# ------------------------------------------------------------------ one plot: zones inside
with st.container(border=True):
    h1, h2, h3 = st.columns([2.2, 1.3, 1.2], vertical_alignment="center")
    with h1:
        pid = ui.pick(st, "selectbox", "Plot", "parcel", ids, format_func=labels.get, label_visibility="collapsed")
    s = zd[0]["plots"][pid]
    today_status = _status(st.session_state["farm"], pd.Timestamp(replay), st.session_state.get("machine", "M2")).get(pid)
    with h2:
        view = st.segmented_control("View", ["zones", "photo"], default="zones", key="zone_view",
                                    label_visibility="collapsed",
                                    format_func=lambda v: "Zones" if v == "zones" else "Photo only")
    with h3:
        if today_status:
            st.markdown(f"<div style='text-align:right'><span style='background:{ui.STATUS_COLORS.get(today_status)};"
                        f"color:white;border-radius:12px;padding:4px 12px;font-size:0.85rem;font-weight:600'>"
                        f"{today_status} on {pd.Timestamp(replay):%d %b} ({st.session_state.get('machine', 'M2')})"
                        f"</span></div>", unsafe_allow_html=True)
    pic, txt = st.columns([1.15, 1], gap="large")
    with pic:
        img = plot_zones.zoom_image(pid, layer if (view or "zones") == "zones" else None)
        if img is not None:
            st.image(img, width="stretch")
    with txt:
        st.markdown(f"<div style='font-size:1.3rem;font-weight:700;margin-bottom:2px'>{ui.field_name(pid)} · "
                    f"{L['title'].lower()}</div><div style='opacity:0.7;font-size:0.85rem;margin-bottom:10px'>"
                    f"{L['sub']}</div>", unsafe_allow_html=True)
        has = layer == "wet" or s.get("ndvi_zone_rel")
        if has:
            vals = s["wet_zone_change_db"] if layer == "wet" else s["ndvi_zone_rel"]
            unit = " dB" if layer == "wet" else " %"
            cells = "".join(
                f"<div style='flex:1;border-radius:10px;padding:8px 10px;background:{plot_zones._hex(c, 0.18)};"
                f"border-left:6px solid {plot_zones._hex(c)}'><div style='font-size:0.78rem;opacity:0.8'>{n}</div>"
                f"<div style='font-size:1.2rem;font-weight:700'>{v:+.1f}{unit}</div></div>"
                for n, c, v in zip(L["names"], L["colors"], vals))
            st.markdown(f"<div style='display:flex;gap:8px;margin:4px 0 10px 0'>{cells}</div>", unsafe_allow_html=True)
        if layer == "wet":
            st.markdown("**Use it:** do the hand test in the dark-blue part first. On a CAUTION day start in the "
                        "driest third and leave the wettest for last; turn and park on the dry side.")
            st.caption("Each zone is a third of the plot. Value: rise of the radar signal after the rain (more = wetter "
                       f"soil surface). On 11 Oct, the demo week, the wettest third was still "
                       f"{s['wet_zone_change_11oct_db'][0]:+.1f} dB above the dry baseline, the driest "
                       f"{s['wet_zone_change_11oct_db'][2]:+.1f} dB. Radar also reacts to roughness and crop residue.")
        elif has:
            word, colour = plot_zones.stability_word(s.get("ndvi_year_corr"))
            st.markdown(f"Pattern: <b style='color:{colour}'>{word}</b> (year-to-year rank correlation "
                        f"{s['ndvi_year_corr']:.2f})", unsafe_allow_html=True)
            st.markdown("**Use it:** look for compacted subsoil or poor drainage in the brown part first; check "
                        "emergence there after a wet sowing." if s["ndvi_year_corr"] >= 0.2 else
                        "Too unstable to act on: the weak part moves from year to year.")
            st.caption(f"Value: spring NDVI of the zone vs the plot median, median of {len(s['ndvi_years'])} "
                       f"closed-canopy years ({', '.join(map(str, s['ndvi_years']))}). NDVI does not measure "
                       "trafficability.")
        else:
            st.caption("Fewer than three closed-canopy springs over this plot: no productivity zones.")
        b1, b2 = st.columns(2)
        if b1.button("Open in Today", type="primary", width="stretch"):
            st.switch_page("views/3_Today.py")
        if b2.button("Farm map", width="stretch"):
            st.switch_page("views/1_Farm.py")
        ui.show_origin("real", False)
        st.caption("Contains modified Copernicus Sentinel data [2016-2024] (CDSE). Orthophoto: GUGiK. The location is "
                   "illustrative: the plots of the synthetic demo farm are drawn on real fields.")

with st.expander("Validation on a real farmer's field: Gąsawy, 80.7 ha (radar vs our soil-water model)"):
    zones_panel.render(inline=True)
lat, lon = prm.SATELLITE["nuts3_latlon"].value.get("PL415", (52.41, 16.93))
st.caption(f"[Open the region in Copernicus Browser](https://browser.dataspace.copernicus.eu/?lat={lat}&lng={lon}&zoom=11)")
