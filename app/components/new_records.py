"""Records created in this session + CSV/JSON download (spec 9.4; Mirela's slice, written by Marek's agent)."""
import pandas as pd
import streamlit as st


def render() -> None:
    recs = st.session_state.get("records", [])
    if not recs:
        with st.container(border=True):
            st.markdown("**No records in this session yet.**")
            st.caption("On the Today page, press **Mark as done** after the work: FieldGo saves the operation together "
                       "with the day's soil status, weather and machine, ready for your farm records.")
            try:
                st.page_link("views/3_Today.py", label="Go to Today", icon="🚜")
            except Exception:  # noqa: BLE001  (page run on its own, without the router)
                pass
        return
    st.caption(f"{len(recs)} record(s) created in this session.")
    df = pd.DataFrame(recs)
    if "parcel_id" in df:
        import ui
        df.insert(0, "plot", df["parcel_id"].map(ui.field_name))
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
