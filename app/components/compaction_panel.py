"""Tyre-based compaction check panel (17 Oct; simplified Terranimo-style chain, engine/compaction.py)."""
import plotly.graph_objects as go
import streamlit as st

import ui

CLASS_AS = {"green": "GO", "yellow": "CAUTION", "red": "NO-GO", "not available": "not available"}
CLASS_WORD = {"green": "below strength", "yellow": "up to 1.5 x strength", "red": "far above strength"}


def _chart(prof) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=prof.stress_kpa, y=prof.depth_m * 100, mode="lines+markers", name="stress under wheel",
                             line=dict(color="#d73027")))
    fig.add_trace(go.Scatter(x=prof.strength_kpa, y=prof.depth_m * 100, mode="lines+markers", name="soil strength today",
                             line=dict(color="#1a9850", dash="dash")))
    fig.add_trace(go.Scatter(x=prof.strength_kpa * 1.5, y=prof.depth_m * 100, mode="lines", name="1.5 x strength (red above)",
                             line=dict(color="#f5a623", dash="dot")))
    fig.add_trace(go.Scatter(x=[50], y=[50], mode="markers", name="50 kPa at 50 cm (rule)",
                             marker=dict(symbol="x", size=12, color="#333")))
    fig.update_yaxes(autorange="reversed", title="depth (cm)")
    fig.update_xaxes(title="vertical stress / strength (kPa)", rangemode="tozero")
    fig.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation="h", y=-0.25))
    return fig


def render(t: dict) -> None:
    c = t.get("compaction")
    if not c:
        return
    with st.container(border=True):
        st.markdown(f"**Compaction check with your tyres** · {c['wheel_load_t']:.2f} t per wheel at "
                    f"{c['inflation_bar']:.1f} bar")
        if not c["assessed"]:
            st.caption(c["reason"])
            return
        d, a, b = st.columns(3)
        with d:
            ui.status_tile("Main test: < 50 kPa at 50 cm", c["rule_50kpa_50cm"].upper(), size="1.2rem",
                           color_as="GO" if c["rule_50kpa_50cm"] == "met" else "NO-GO")
        with a:
            ui.status_tile("Subsoil (30-80 cm, lasts years)", c["subsoil"].upper(), size="1.2rem",
                           color_as=CLASS_AS[c["subsoil"]])
        with b:
            ui.status_tile("Topsoil (10-20 cm)", c["topsoil"].upper(), size="1.2rem", color_as=CLASS_AS[c["topsoil"]])
        st.caption(f"Subsoil strength: {c.get('subsoil_strength_source', 'default')}. The 50 kPa rule needs no strength "
                   "estimate (Schjønning et al. 2012); if it is exceeded, the subsoil is at least yellow.")
        st.caption(f"Contact pressure {c['mgp_kpa']:.0f} kPa on {c['area_m2']:.2f} m² · soil wetness pF {c['pf']:.2f} "
                   f"(modelled) · stress at 50 cm {c['stress_50cm_kpa']:.0f} kPa · the 50 kPa line reaches "
                   f"{c['depth_50kpa_m'] * 100:.0f} cm")
        st.plotly_chart(_chart(c["profile"]), width="stretch")
        strip = " · ".join(f"{s['date']:%a %d}: {s['subsoil']}" for s in c.get("strip72", []))
        if strip:
            st.caption("Subsoil, next 72 h: " + strip)
        for lv in c.get("levers") or []:
            if lv["lever"] == "lower tyre pressure":
                st.markdown(f"- **Lower tyre pressure to {lv['inflation_bar']:.1f} bar** -> subsoil {lv['subsoil']}, "
                            f"topsoil {lv['topsoil']}. {lv['note']}")
            else:
                st.markdown(f"- **Wheel load ≤ {lv['wheel_load_t']:.2f} t** (axle ≤ {lv['axle_load_t']:.1f} t) -> "
                            f"subsoil {lv['subsoil']}. {lv['note']}")
        st.caption("Rules of thumb (Terranimo): tyre pressure drives topsoil stress, wheel load drives subsoil stress; "
                   "wetter soil is weaker and carries the stress deeper. Tilled topsoil is usually above its strength "
                   "and recovers with tillage, wet-dry and frost cycles; subsoil damage lasts for years.")
        with st.expander("How this is calculated, limits and sources"):
            st.markdown(
                "1. Contact pressure = inflation pressure + carcass stiffness; footprint = wheel load / pressure.\n"
                "2. Stress under the wheel centre: Söhne/Fröhlich, uniform circular footprint; the concentration "
                "factor rises with wetness (6 at pF 1.7, 5 at pF 2.0, 4 at pF 2.7).\n"
                "3. Soil strength (precompression stress) from clay and pF, fitted to the anchor values of the "
                "Terranimo note; at pF 2 it does not depend on clay.\n"
                "4. Class per depth from SCI = log10(stress / strength): green ≤ 0, yellow ≤ 0.18, red above.")
            for n in c["notes"]:
                st.caption(n)
            st.caption("Sources: " + c["sources"] + ". Label: " + c["label"] + ".")
        ui.show_origin(c["origin"], False)
