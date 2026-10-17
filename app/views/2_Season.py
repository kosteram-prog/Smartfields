"""Season page (owner: Marek, spec 9.2): P(finish by deadline), contractor, cost of delay, charts A and B."""
import datetime as dt

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import config
import ui
from components import cost_cards
from engine import params as prm

ui.shell("Season")
REAL = config.data_dir_or_none() is not None
if REAL:
    from engine.season import season as run_season
else:
    from engine.stubs import season as run_season
    st.warning("FIELDGO_DATA_DIR is not set: showing stub numbers. Set it to the extracts folder and restart.")


@st.cache_data(show_spinner="Simulating 10 autumns...")
def simulate(params: dict) -> dict:
    return run_season(params)


# ------------------------------------------------------------------ inputs
with st.expander("Inputs", expanded=True):
    c = st.columns(4)
    start = c[0].date_input("Window start", dt.date(2016, *map(int, prm.SEASON["window_start"].value.split("-"))),
                            format="DD.MM.YYYY", help="Year is ignored: every autumn 2015-2024 is simulated")
    deadline = c[1].date_input("Deadline", dt.date(2016, *map(int, prm.SEASON["deadline"].value.split("-"))),
                               format="DD.MM.YYYY")
    machine = ui.pick(c[2], "selectbox", "Machine", "machine", list(prm.MACHINES),
                             format_func=lambda m: f"{m}: {prm.MACHINES[m]['profile']}")
    units = c[3].number_input("Own units", 1, 5, int(prm.CAPACITY["own_units"].value))
    c = st.columns(4)
    hours = c[0].number_input("Hours per day", 4, 16, int(prm.CAPACITY["hours_per_day"].value))
    contractor = c[1].number_input("Contractor (extra ha/day)", 0, 60, 0, step=5)
    c_start = c[2].date_input("Contractor from", start, format="DD.MM.YYYY")
    caution = c[3].radio("CAUTION day counts as", list(prm.SEASON["caution_weight_options"].value), index=1,
                         horizontal=True, format_func=lambda x: f"{x:g} day")
    c = st.columns(4)
    m2 = c[0].selectbox("Second machine (optional)", ["none"] + list(prm.MACHINES), index=0,
                        format_func=lambda m: "none" if m == "none" else f"{m}: {prm.MACHINES[m]['profile']}",
                        help="Large farms run several drills: capacities add up; the day status follows the "
                             "heaviest machine (conservative).")
    u2 = c[1].number_input("Units of the second machine", 0, 5, 1 if m2 != "none" else 0, disabled=m2 == "none")
    fleet = ((m2, int(u2)),) if m2 != "none" and u2 > 0 else ()
    rate = prm.MACHINES[machine]["rate_ha_h"].value
    cap = units * rate * hours + sum(u * prm.MACHINES[mid]["rate_ha_h"].value * hours for mid, u in fleet)
    heavy = max([prm.MACHINES[machine]["load_class"]] + [prm.MACHINES[mid]["load_class"] for mid, _ in fleet],
                key=lambda x: int(x[1:]))
    st.caption(f"Own capacity: **{cap:.0f} ha/day** "
               + (f"({units} × {machine} + {fleet[0][1]} × {fleet[0][0]}, {hours} h)" if fleet else
                  f"({units} × {rate} ha/h × {hours} h)")
               + f" · day status for class {heavy} · rates and hours are assumptions")

md = lambda d: d.strftime("%m-%d")  # noqa: E731
params = {"window_start": md(start), "deadline": md(deadline), "machine_id": machine, "units": int(units),
          "hours": float(hours), "contractor_ha_day": float(contractor), "contractor_start": md(c_start),
          "caution_weight": float(caution), "fleet": fleet}
if st.session_state.get("parcel_order"):
    params["parcel_order"] = tuple(st.session_state["parcel_order"])
res = simulate(params)
stub = not REAL
if res.get("message"):
    st.info(res["message"])
    st.stop()

# ------------------------------------------------------------------ headline
p_own = res["P_by_deadline"]
p_with = res.get("P_by_deadline_with_contractor")
dl = deadline.strftime("%d %b")
b1, b2, b3 = st.columns(3)
with b1:
    ui.metric(f"Chance to finish by {dl} (own machines)", f"{p_own['value']:.0%}", p_own["origin"], stub,
              help=f"Share of the {p_own.get('n_years', 10)} historical autumns in which every plot is sown by the deadline")
with b2:
    if p_with:
        ui.metric(f"With contractor +{contractor} ha/day", f"{p_with['value']:.0%}", p_with["origin"], stub)
rec = res["contractor_recommendation"]
if not p_with:
    with b2:
        if isinstance(rec.get("p_with"), (int, float)) and isinstance(rec.get("extra_ha_day"), (int, float)) \
                and rec["extra_ha_day"] > 0:
            ui.metric(f"With the recommended contractor (+{rec['extra_ha_day']:g} ha/day)", f"{rec['p_with']:.0%}",
                      rec["origin"], stub, help="Smallest contractor capacity that reaches the target share of autumns. "
                                                 "Set 'Contractor (extra ha/day)' above to try your own.")
        else:
            st.metric("With contractor", "not needed" if p_own["value"] >= rec.get("target_p", 0.9) else "not available")
with b3, st.container(border=True):
    st.markdown("**Recommendation**")
    st.write(rec.get("message") or "not available")
    if isinstance(rec.get("extra_ha_day"), (int, float)) and rec["extra_ha_day"] > 0:
        if isinstance(rec.get("ha_median"), (int, float)):
            st.caption(f"Reaches {rec['p_with']:.0%} of autumns; contractor sows ~{rec['ha_median']:.0f} ha in the median year.")
    ui.show_origin(rec["origin"], stub)

sens = res["sensitivity"]
st.caption(f"Sensitivity: P = {sens[0.5]:.0%} if a CAUTION day counts as ½ day · {sens[0.0]:.0%} if 0 · "
           f"{sens[1.0]:.0%} if 1 day. The CAUTION rule matters as much as the weather.")

# ------------------------------------------------------------------ cost (Mirela's component)
st.subheader("Cost of delay")
cost_cards.render(res.get("schedule"), None, params)

# ------------------------------------------------------------------ chart A: completion per year
st.subheader("When is sowing finished? One bar per historical autumn")
comp = res["completion"].copy()
base = pd.Timestamp(f"2000-{md(start)}")
end_md = prm.SEASON["simulation_end"].value


def day_no(y, d):
    return (pd.Timestamp(d) - pd.Timestamp(f"{y}-{md(start)}")).days + 1 if pd.notna(d) else None


comp["day"] = [day_no(y, d) for y, d in zip(comp.year, comp.completion_date)]
dl_day = (pd.Timestamp(f"2000-{md(deadline)}") - base).days + 1
max_day = (pd.Timestamp(f"2000-{end_md}") - base).days + 1
late = [d is None or d > dl_day for d in comp.day]
fig = go.Figure(go.Bar(
    y=comp.year.astype(str), x=[d if d is not None else max_day for d in comp.day], orientation="h",
    marker=dict(color=[ui.STATUS_COLORS["NO-GO"] if lt else ui.STATUS_COLORS["GO"] for lt in late],
                cornerradius=4),
    text=[pd.Timestamp(c).strftime("%d %b") if pd.notna(c) else "not done by 30 Nov" for c in comp.completion_date],
    textposition="outside", cliponaxis=False,
    customdata=[["late" if lt else "on time"] for lt in late],
    hovertemplate="%{y}: done %{text} (%{customdata[0]})<extra></extra>"))
fig.add_vline(x=dl_day, line_dash="dash", line_color="#555", annotation_text=f"deadline {dl}",
              annotation_position="top")
ticks = list(range(1, max(comp.day.dropna().max() if comp.day.notna().any() else dl_day, dl_day) + 6, 5))
fig.update_layout(height=360, margin=dict(l=10, r=40, t=30, b=10), showlegend=False, bargap=0.35,
                  xaxis=dict(tickvals=ticks, ticktext=[(base + pd.Timedelta(days=t - 1)).strftime("%d %b") for t in ticks],
                             gridcolor="#eee", title=None),
                  yaxis=dict(autorange="reversed", title=None, type="category", tickmode="linear"), plot_bgcolor="white")
st.plotly_chart(fig, width="stretch")
ui.show_origin("real+modelled", stub)
st.caption("Green = finished by the deadline, red = late. 10 weather scenarios = AgERA5 2015-2024 for PL415 "
           "(regional weather). Capacity and thresholds are editable assumptions.")

# ------------------------------------------------------------------ chart B: workable-day strip
wd = res.get("workable_days")
if isinstance(wd, pd.DataFrame) and not wd.empty:
    st.subheader("Workable days: share of the sowing area with status GO")
    w = wd.copy()
    w["md"] = pd.to_datetime(w.date).dt.strftime("%d %b")
    w["doy"] = (pd.to_datetime(w.date) - pd.to_datetime(w.year.astype(str) + "-" + md(start))).dt.days
    grid = w.pivot_table(index="year", columns="doy", values="share_go")
    labels = w.drop_duplicates("doy").set_index("doy").md.reindex(grid.columns)
    heat = go.Figure(go.Heatmap(
        z=grid.values, x=labels.values, y=grid.index.astype(str), zmin=0, zmax=1,
        colorscale=[[0, "#f2f2f2"], [0.5, "#a1d99b"], [1, "#1a7a3c"]], xgap=2, ygap=2,
        colorbar=dict(title="GO share", tickformat=".0%", len=0.8),
        hovertemplate="%{y} %{x}: %{z:.0%} of the area GO<extra></extra>"))
    heat.update_layout(height=340, margin=dict(l=10, r=10, t=10, b=10),
                       yaxis=dict(autorange="reversed", type="category", tickmode="linear"),
                       xaxis=dict(nticks=12), plot_bgcolor="white")
    st.plotly_chart(heat, width="stretch")
    ui.show_origin("real+modelled", stub)
    w16 = w[(w.year == 2016) & (w.doy < 21)]
    n16 = int((w16["share_go_parcels" if "share_go_parcels" in w16 else "share_go"] >= 0.5).sum())
    st.caption(f"Autumn 2016: only {n16} days in the first three weeks with GO on at least half of the plots "
               f"(machine class {prm.MACHINES[machine]['load_class']}).")

# ------------------------------------------------------------------ parcel order
st.subheader("Plot order")
order = pd.DataFrame(res["parcel_order"])
if not order.empty:
    order.insert(1, "plot", order["parcel_id"].map(ui.field_name))
if REAL and not order.empty:
    with st.expander("Change the order (your own priorities)"):
        st.caption("Edit the rank numbers and press Apply; the season is re-simulated with your order.")
        ed = st.data_editor(order[["rank", "plot", "crop", "area_ha", "clay_pct", "parcel_id"]], hide_index=True,
                            disabled=["plot", "parcel_id", "crop", "area_ha", "clay_pct"], key="order_editor")
        b1, b2 = st.columns(2)
        if b1.button("Apply my order"):
            st.session_state["parcel_order"] = list(ed.sort_values("rank").parcel_id)
            st.rerun()
        if b2.button("Back to the default priority"):
            st.session_state.pop("parcel_order", None)
            st.rerun()
    if st.session_state.get("parcel_order"):
        st.info("Using your own plot order instead of the default priority.")
if not order.empty:
    import re
    short = lambda r: re.sub(r"\s*\((?:tolerates later sowing)\)|, clay \d+%|\s*\d+(?:\.\d+)? ha", "",  # noqa: E731
                             str(r)).replace("(less tolerant of late sowing)", "(sensitive to late sowing)") \
        .replace(" (sow while dry)", ": sow while dry").replace("large plot", "large")
    order = order.assign(why=order["reason"].map(short)) if "reason" in order.columns else order
    cols = [c for c in ["rank", "plot", "crop", "area_ha", "clay_pct", "median_done", "why"] if c in order.columns]
    st.dataframe(order[cols], hide_index=True, width="stretch",
                 column_config={"why": "why this order", "median_done": "usually done (median)",
                     "area_ha": st.column_config.NumberColumn("Area (ha)", format="%.1f"),
                     "clay_pct": st.column_config.NumberColumn("Clay %", format="%.0f")})
    ui.show_origin("synthetic+assumption+modelled", stub)
    st.caption("Heavy soils first while they are dry; rapeseed and barley are less tolerant of late sowing than wheat.")

