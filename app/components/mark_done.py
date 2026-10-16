"""Owner: Mirela. 'Mark as done' button creating a record (stub version)."""
import streamlit as st

from engine import stubs  # TODO: engine.records.make_record


def render(today_result: dict, parcel_id: str, operation: str) -> None:
    status = today_result.get("status")
    overridden = False
    if status in ("CAUTION", "NO-GO"):
        overridden = st.checkbox(f"Override: status is {status}, I did it anyway", key="override")
    if st.button("Mark as done", disabled=status in ("CAUTION", "NO-GO") and not overridden):
        rec = stubs.make_record(today_result, parcel_id, operation, overridden)
        st.session_state.setdefault("records", []).append(rec)
        st.success("Record created (see Records > New records).")
