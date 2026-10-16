"""Shared UI helpers (kickoff, shared file): page shell, origin badges, stub badge, status colours.

No agronomy here. Pages import it as `import ui` (Streamlit puts the folder of app/main.py on sys.path).
"""
from __future__ import annotations

import datetime as dt

import streamlit as st

from engine import params as prm

STATUS_COLORS = {"GO": "#1a9850", "CAUTION": "#f5a623", "NO-GO": "#d73027", "not available": "#9e9e9e"}
ORIGIN_COLORS = {"real": "#1f77b4", "modelled": "#8e44ad", "synthetic": "#e67e22", "assumption": "#7f8c8d"}
BANNER = "Replay mode: historical AgERA5 weather is used as the forecast"


def _pill(text: str, color: str) -> str:
    return (f"<span style='background:{color};color:white;border-radius:10px;padding:1px 8px;"
            f"font-size:0.72rem;margin-right:4px;white-space:nowrap'>{text}</span>")


def origin_badges(origin: str) -> str:
    """HTML pills for an origin string such as 'real+synthetic+assumption'."""
    return "".join(_pill(o, ORIGIN_COLORS.get(o, "#999")) for o in str(origin).split("+"))


def stub_badge() -> str:
    return _pill("stub", "#c0392b")


def show_origin(origin: str, stub: bool = True) -> None:
    st.markdown(origin_badges(origin) + (stub_badge() if stub else ""), unsafe_allow_html=True)


def metric(label: str, value, origin: str, stub: bool = True, help: str | None = None) -> None:
    st.metric(label, value, help=help)
    show_origin(origin, stub)


def status_tile(label: str, status: str, size: str = "2.4rem", color_as: str | None = None) -> None:
    """Coloured tile; color_as lets another word (e.g. 'HIGH') use a status colour ('NO-GO')."""
    color = STATUS_COLORS.get(color_as or status, STATUS_COLORS["not available"])
    st.markdown(
        f"<div style='background:{color};color:white;border-radius:12px;padding:14px 18px;text-align:center'>"
        f"<div style='font-size:0.9rem;opacity:0.9'>{label}</div>"
        f"<div style='font-size:{size};font-weight:700'>{status}</div></div>", unsafe_allow_html=True)


def fmt_eur(x) -> str:
    return "not available" if not isinstance(x, (int, float)) else f"EUR {x:,.0f}"


def shell(title: str) -> dt.date:
    """Page config, sidebar (farm, replay date), mode banner and origin legend. Returns the replay date."""
    st.set_page_config(page_title=f"FieldGo - {title}", page_icon="🌾", layout="wide")
    with st.sidebar:
        st.markdown("### 🌾 FieldGo")
        st.selectbox("Farm", [prm.DEMO["holding_id"].value], key="farm",
                     help="FARM-13525 (PL415, Poznan region) is the only demo farm.")
        lo, hi = prm.DEMO["replay_year_min"].value, prm.DEMO["replay_year_max"].value
        st.date_input("Replay date", value=dt.date.fromisoformat(prm.DEMO["replay_date"].value),
                      min_value=dt.date(lo, 1, 1), max_value=dt.date(hi, 12, 31), key="replay_date")
        st.caption("Data origin")
        st.markdown(
            "".join(f"<div>{_pill(k, ORIGIN_COLORS[k])} <small>{v}</small></div>" for k, v in prm.ORIGINS.items()),
            unsafe_allow_html=True)
        st.markdown(f"<div style='margin-top:8px'>{stub_badge()} <small>placeholder number from engine/stubs.py</small></div>",
                    unsafe_allow_html=True)
    st.info(BANNER, icon="⏪")
    st.title(title)
    return st.session_state["replay_date"]
