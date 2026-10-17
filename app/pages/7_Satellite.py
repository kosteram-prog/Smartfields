"""Satellite page (owner: Mirela): Copernicus / Sentinel view with env-token + public fallback."""
from __future__ import annotations

import os

import streamlit as st
import streamlit.components.v1 as components

import ui
from engine import params as prm
from engine import stubs

ui.shell("Satellite")
st.caption(
    "Sentinel imagery over the demo farm region. Optional "
    f"`{prm.SATELLITE['env_token_name'].value}` enables a live CDSE connection path; "
    "without it, public EOX Sentinel-2 cloudless tiles still show."
)

fs = stubs.farm_summary(st.session_state["farm"])
nuts = fs["nuts3"]
coords = prm.SATELLITE["nuts3_latlon"].value
lat, lon = coords.get(nuts, (52.41, 16.93))
token_name = prm.SATELLITE["env_token_name"].value
token = os.environ.get(token_name, "").strip()
tiles = prm.SATELLITE["fallback_tiles"].value

if token:
    st.success(
        f"{token_name} is set in the environment (not stored in the repo). "
        "Map still uses the public Sentinel mosaic in this prototype; the token is "
        "ready for a CDSE Process API / OGC backend."
    )
    ui.show_origin("assumption", stub=False)
else:
    st.info(
        f"No {token_name} — showing public Sentinel-2 cloudless tiles (EOX). "
        f"To prepare live CDSE access: `export {token_name}=...` then restart Streamlit."
    )
    ui.show_origin("real", stub=False)

st.write(f"**{fs['holding_id']}** · NUTS3 `{nuts}` · map centre ≈ {lat:.2f}, {lon:.2f}")

html = f"""
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<div id="m" style="height:420px;border-radius:12px;"></div>
<script>
  var map = L.map('m').setView([{lat}, {lon}], 11);
  L.tileLayer({tiles!r}, {{
    maxZoom: 16,
    attribution: '&copy; EOX Sentinel-2 cloudless / Copernicus'
  }}).addTo(map);
  L.circle([{lat}, {lon}], {{radius: 4000, color: '#2f7a43', fillOpacity: 0.08}}).addTo(map);
</script>
"""
components.html(html, height=440)

browse = (
    "https://browser.dataspace.copernicus.eu/"
    f"?lat={lat}&lng={lon}&zoom=11"
)
st.markdown(f"[Open this area in Copernicus Browser]({browse})")
st.caption(
    "Fallback tiles need network access to the EOX CDN. No datasets or tokens are committed."
)
