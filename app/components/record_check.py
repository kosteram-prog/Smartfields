"""Owner: Marek. 'Record check' tab: RecordLint root-cause cards with drill-down (spec 7.13, 9.4)."""
import streamlit as st

import config
import ui

REAL = config.data_dir_or_none() is not None
if REAL:
    from engine.lint import lint_records
else:
    from engine.stubs import lint_records


@st.cache_data(show_spinner="Checking records...")
def _run(holding_id, campaign):
    return lint_records(holding_id, campaign)


def render(holding_id: str, campaign=2024) -> None:
    res = _run(holding_id, campaign)
    stub = not REAL
    scope = f"{campaign} campaign" if campaign else "all campaigns 2017-2026"
    issues = [c for c in res["cards"] if c.get("severity", "issue") == "issue"]
    checks = [c for c in res["cards"] if c.get("severity") == "check"]
    c1, c2, c3 = st.columns(3)
    with c1:
        ui.metric(f"Records ({scope})", f"{res['n_records']:,}", res["origin"], stub)
    with c2:
        ui.metric("Flags", f"{res['n_flags']:,}", res["origin"], stub)
    with c3:
        ui.metric("Root causes to fix", len(issues), res["origin"], stub,
                  help="Flags grouped by cause: fix the cause once instead of row by row")
    if not res["cards"]:
        st.success("No issues found by rules R1-R6.")
        return
    for c in issues + checks:
        icon = "🔴" if c.get("severity", "issue") == "issue" else "🟡"
        with st.container(border=True):
            st.markdown(f"{icon} **{c['title']}** · {c['n_rows']} rows"
                        + (f" on {c['n_parcels']} parcels" if "n_parcels" in c else "") + f" · rule {c['rule']}")
            st.write(c["why"])
            st.markdown(f"**Suggested fix:** {c['fix']}")
            with st.expander(f"Show the {c['n_rows']} rows"):
                st.dataframe(c["rows"], hide_index=True, width="stretch")
    st.caption("Records are synthetic (organisers' dataset); weather for R3/R6 is regional AgERA5. "
               "Plant-protection dose units are flagged 'unresolved L or kg/ha' by the organisers.")
