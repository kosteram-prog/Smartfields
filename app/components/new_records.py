"""Records created in this session + CSV/JSON download (spec 9.4; Mirela's slice, written by Marek's agent)."""
import pandas as pd
import streamlit as st


def render() -> None:
    recs = st.session_state.get("records", [])
    if not recs:
        st.info("No records yet. Use 'Mark as done' on the Today page.")
        return
    df = pd.DataFrame(recs)
    for col in df.columns:
        if df[col].map(lambda v: isinstance(v, (list, dict))).any():
            df[col] = df[col].map(lambda v: ", ".join(v) if isinstance(v, list) else str(v))
    if "missing_fields" in df:
        n = (df["missing_fields"].astype(str).str.len() > 0).sum()
        if n:
            st.warning(f"{n} record(s) miss fields required for plant-protection records (Reg. (EU) 2023/564).")
    st.dataframe(df, hide_index=True, width="stretch")
    st.download_button("Download CSV", df.to_csv(index=False), "fieldgo_records.csv", "text/csv")
    st.download_button("Download JSON", df.to_json(orient="records", date_format="iso"),
                       "fieldgo_records.json", "application/json")
