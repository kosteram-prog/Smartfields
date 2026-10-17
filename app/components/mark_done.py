"""'Mark as done' creates a record with the day's conditions (spec 7.11; Mirela's slice, written by Marek's agent)."""
import streamlit as st

import config

REAL = config.data_dir_or_none() is not None


def render(today_result: dict, parcel_id: str, operation: str) -> None:
    status = today_result.get("status")
    with st.container(border=True):
        st.markdown("**Mark as done** (creates a record with today's conditions)")
        product = dose = unit = None
        if operation in ("spraying", "fertilising"):
            c = st.columns(3)
            product = c[0].text_input("Product name", key="rec_product")
            dose = c[1].number_input("Dose", min_value=0.0, value=None, key="rec_dose")
            unit = c[2].selectbox("Unit", ["L/ha", "kg/ha"], key="rec_unit")
        overridden = False
        if status in ("CAUTION", "NO-GO"):
            overridden = st.checkbox(f"Override: the status was {status}, I did it anyway (recorded)", key="override")
        if st.button("Mark as done", disabled=status in ("CAUTION", "NO-GO") and not overridden):
            if REAL:
                from engine.records import make_record
                rec = make_record(today_result, parcel_id, operation, overridden, product, dose, unit)
            else:
                from engine import stubs
                rec = stubs.make_record(today_result, parcel_id, operation, overridden)
            st.session_state.setdefault("records", []).append(rec)
            missing = rec.get("missing_fields") or []
            st.success(f"Record {rec['record_id']} created (Records > New records)."
                       + (f" Fill in: {', '.join(missing)}." if missing else ""))
