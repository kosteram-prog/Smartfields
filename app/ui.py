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


SHARED = {"machine": "M2", "parcel": "PARCEL-0149869", "load": 100, "operation": "sowing"}   # B4: kept across pages


def init_state() -> None:
    """Defaults for the shared selections (farm, replay date, machine, parcel, load, operation)."""
    st.session_state.setdefault("farm", prm.DEMO["holding_id"].value)
    st.session_state.setdefault("replay_date", dt.date.fromisoformat(prm.DEMO["replay_date"].value))
    for k, v in SHARED.items():
        st.session_state.setdefault(k, v)


def sidebar(real: bool = True) -> None:
    """Shared sidebar, rendered once by the router (app/main.py) so its values survive page switches."""
    init_state()
    with st.sidebar:
        st.markdown("### 🌾 FieldGo")
        st.selectbox("Farm", [prm.DEMO["holding_id"].value], key="farm",
                     help="FARM-13525 (PL415, Poznan region) is the only demo farm.")
        lo, hi = prm.DEMO["replay_year_min"].value, prm.DEMO["replay_year_max"].value
        st.date_input("Replay date", min_value=dt.date(lo, 1, 1), max_value=dt.date(hi, 12, 31), key="replay_date",
                      help="The app replays a past day: the weather that followed plays the forecast.")
        with st.expander("Data origin labels"):
            st.markdown(
                "".join(f"<div>{_pill(k, ORIGIN_COLORS[k])} <small>{v}</small></div>" for k, v in prm.ORIGINS.items())
                + ("" if real else f"<div style='margin-top:8px'>{stub_badge()} <small>placeholder number</small></div>"),
                unsafe_allow_html=True)


def pick(container, kind: str, label: str, name: str, options=None, **kw):
    """A widget whose value is shared across pages (B4): parcel, machine, load, operation.

    Streamlit drops a widget's state when the page changes; the value lives in st.session_state[name] instead.
    """
    init_state()
    wkey = f"_w_{name}"
    if options is not None and st.session_state[name] not in list(options):
        st.session_state[name] = list(options)[0]
    st.session_state[wkey] = st.session_state[name]       # re-seed: the widget may be new on this page

    def _sync():
        st.session_state[name] = st.session_state[wkey]
    fn = getattr(container, kind)
    args = (label, options) if options is not None else (label,)
    return fn(*args, key=wkey, on_change=_sync, **kw)


def shell(title: str) -> dt.date:
    """Mode banner and page title. Returns the replay date (shared, set in the sidebar)."""
    init_state()
    st.info(BANNER, icon="⏪")
    st.title(title)
    return st.session_state["replay_date"]


# --------------------------------------------------------------------------- farmer-friendly words (A3, A4)
CROP_WORDS = {"BARL": "barley", "COWT": "wheat", "RAPE": "rapeseed", "MAIZ": "maize", "SUNF": "sunflower",
              "HAY": "grass/hay", "OLIV": "olives"}


def field_name(parcel_id: str) -> str:
    """Short field name from a parcel id: PARCEL-0149869 -> 'Field 869' (unique on the demo farm)."""
    return f"Field {str(parcel_id)[-3:]}"


def soil_word(clay_pct, sand_pct) -> str:
    if clay_pct is None or sand_pct is None:
        return "soil n/a"
    if clay_pct >= 40:
        return "heavy clay"
    if clay_pct >= 25:
        return "clay loam"
    if sand_pct >= 70:
        return "sand"
    if sand_pct >= 50:
        return "sandy loam"
    return "loam"


def parcel_label(pid, crop, area_ha, clay_pct, sand_pct) -> str:
    return (f"{field_name(pid)} · {CROP_WORDS.get(crop, crop)} · {area_ha:.1f} ha · "
            f"{soil_word(clay_pct, sand_pct)}")


def humanize(text: str) -> str:
    """Replace parcel ids in engine text by field names."""
    import re
    return re.sub(r"PARCEL-\d*?(\d{3})\b", lambda m: f"Field {m.group(1)}", str(text))


def wetness_words(rwc_eff) -> str:
    if rwc_eff is None:
        return "soil water not available"
    if rwc_eff >= 1.05:
        return "the topsoil is wetter than field capacity (just after rain)"
    if rwc_eff >= 0.95:
        return "the topsoil is at field capacity (as wet as it stays after draining)"
    if rwc_eff >= 0.85:
        return "the topsoil is moist, close to field capacity"
    if rwc_eff >= 0.7:
        return "the topsoil is moist but has started to dry"
    return "the topsoil is dry enough"


def plain_reasons(t: dict) -> list[str]:
    """One or two farmer sentences from a Today result; the technical reasons stay in an expander."""
    s, cond = t.get("status"), t.get("conditions") or {}
    machine = t.get("machine_id")
    prof = prm.MACHINES.get(machine, {}).get("profile", machine)
    out = []
    head = {"GO": "Go ahead", "CAUTION": "Only with care", "NO-GO": "Better not today"}.get(s, "Not available")
    out.append(f"**{head}:** {wetness_words(cond.get('rwc_eff'))}, and the soil "
               + ("can carry" if s == "GO" else "is too soft for") + f" a {str(prof).lower()} "
               f"({t.get('axle_load_t')} t per axle).")
    for r in t.get("reasons", []):
        low = r.lower()
        if "rain today" in low:
            out.append("It is raining today.")
        elif "previous 24 h" in low:
            out.append("Heavy rain yesterday: the surface is still soft.")
        elif "frozen soil" in low and "no fertilising" in low:
            out.append("The soil is frozen: no fertilising (nitrate rules).")
        elif "frozen soil" in low:
            out.append("The soil is frozen and carries light and medium machines.")
        elif "passes" in low:
            out.append("Several passes on the same day make it stricter.")
        elif "moisture deficit" in low:
            out.append("Heavy machine: the soil should be at least 10 mm drier than field capacity.")
        elif "wind" in low:
            out.append("Too windy for spraying.")
        elif "rain" in low and "sowing" in low:
            out.append("Some rain today: not ideal for sowing.")
    return out
