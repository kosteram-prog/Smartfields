"""Owner: Marek. RecordLint tab: root-cause cards with drill-down (stub version)."""
import streamlit as st

import ui
from engine import stubs  # TODO: engine.lint.lint_records


def render(holding_id: str, campaign: int = 2024) -> None:
    res = stubs.lint_records(holding_id, campaign)
    st.markdown(f"**{res['n_records']} records, {res['n_flags']} flags -> {len(res['cards'])} root cause(s)**")
    ui.show_origin(res["origin"])
    for c in res["cards"]:
        with st.container(border=True):
            st.markdown(f"**{c['title']}**  ·  {c['n_rows']} rows  ·  rule {c['rule']}")
            st.write(c["why"])
            st.write(f"Suggested fix: {c['fix']}")
            with st.expander("Show rows"):
                st.dataframe(c["rows"], hide_index=True)
