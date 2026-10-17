"""'If you go now' line (spec 7.15 item 2, Add-on 3 / 6.8.3): illustrative year-1 loss from traffic on wet soil.

Default: the 6.8.3 table (status x axle-load class). With the farmer's tyre pressure (17 Oct, proposed) a second line
uses the tyre-based compaction class of the subsoil to pick the table row (engine.cost.entry_cost_tyre).
"""
import streamlit as st

import config
import ui

REAL = config.data_dir_or_none() is not None


def _line(e: dict, prefix: str) -> None:
    if e.get("eur") == "not available" and e.get("message"):
        st.caption(f"{prefix}: {e['message']}")
        return
    if e.get("message") and e.get("eur") == 0:
        st.markdown(f"**{prefix}: {ui.fmt_eur(e['eur'])}** <small>(soil carries this load)</small>",
                    unsafe_allow_html=True)
        return
    extra = (f" · {e['loss_pct']:g}% year-1 loss on ~{e.get('trafficked_ha', '?')} ha trafficked"
             if isinstance(e.get("loss_pct"), (int, float)) and e["loss_pct"] > 0 else
             " · light machine: compaction loss not counted (L1-L2)")
    st.markdown(f"**{prefix}: {ui.fmt_eur(e['eur'])}** <small>(illustrative{extra})</small>", unsafe_allow_html=True)


def render(today_result: dict) -> None:
    if not REAL or today_result.get("status") not in ("GO", "CAUTION", "NO-GO"):
        return
    from engine.cost import entry_cost, entry_cost_tyre
    args = (today_result["load_class"], today_result.get("crop"), today_result.get("area_ha"))
    e = entry_cost(today_result["status"], *args)
    comp = today_result.get("compaction")
    _line(e, "If you go now" if not comp else "If you go now (table)")
    if comp:
        et = entry_cost_tyre(comp, *args)
        _line(et, f"With your tyres ({comp.get('inflation_bar', 0):.1f} bar, subsoil {comp.get('subsoil', '?')})")
    st.caption(e["note"] + " Anchor: Håkansson multi-site study (10-12 t axle ~15% year-1 loss); "
               "values for lighter classes are interpolated and need calibration.")
    ui.show_origin(e["origin"], False)
