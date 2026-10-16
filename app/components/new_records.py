"""Owner: Mirela. Records created in this session + CSV/JSON download (stub version)."""
import pandas as pd
import streamlit as st


def render() -> None:
    recs = st.session_state.get("records", [])
    if not recs:
        st.info("No records yet. Use 'Mark as done' on the Today page.")
        return
    df = pd.DataFrame(recs)
    df["conditions"] = df["conditions"].astype(str)
    st.dataframe(df, hide_index=True)
    st.download_button("Download CSV", df.to_csv(index=False), "fieldgo_records.csv", "text/csv")
    st.download_button("Download JSON", df.to_json(orient="records", date_format="iso"),
                       "fieldgo_records.json", "application/json")
