"""'If you go now' line (spec 7.15 item 2, Add-on 3 / 6.8.3): illustrative year-1 loss from traffic on wet soil."""
import streamlit as st

import config
import ui

REAL = config.data_dir_or_none() is not None


def render(today_result: dict) -> None:
    if not REAL or today_result.get("status") not in ("GO", "CAUTION", "NO-GO"):
        return
    from engine.cost import entry_cost
    e = entry_cost(today_result["status"], today_result["load_class"], today_result.get("crop"),
                   today_result.get("area_ha"))
    if e.get("message"):
        st.markdown(f"**If you go now: {ui.fmt_eur(e['eur'])}** <small>(soil carries this load)</small>",
                    unsafe_allow_html=True)
    else:
        extra = (f" · {e['loss_pct']:g}% year-1 loss on ~{e.get('trafficked_ha', '?')} ha trafficked"
                 if isinstance(e.get("loss_pct"), (int, float)) and e["loss_pct"] > 0 else
                 " · light machine: compaction loss not counted (L1-L2)")
        st.markdown(f"**If you go now: {ui.fmt_eur(e['eur'])}** <small>(illustrative{extra})</small>",
                    unsafe_allow_html=True)
        st.caption(e["note"] + " Anchor: Håkansson multi-site study (10-12 t axle ~15% year-1 loss); "
                   "values for lighter classes are interpolated and need calibration.")
    ui.show_origin(e["origin"], False)
