"""Tests for engine/explain.py (spec 7.14): the AI rewrite can never change a value or the decision."""
import pandas as pd

from engine import explain

T = {"status": "CAUTION", "machine_id": "M2", "load_class": "L2", "parcel_id": "PARCEL-0149869",
     "date": pd.Timestamp("2016-10-13"), "reasons": ["Soil water RWC_eff 0.99 vs GO <= 0.90, CAUTION <= 1.00 for L2"],
     "conditions": {"precip_mm": 0.1, "precip_last48h_mm": 4.1, "rwc_eff": 0.985}, "days_to_first_go": "beyond 72 h",
     "confidence": 45, "best_next_check": "Ball/ribbon hand test."}


def test_template_contains_decision_and_values():
    s = explain.template(T)
    assert "CAUTION" in s and "0.99" in s and "45%" in s


def test_good_rewrite_is_accepted_and_labelled():
    r = explain.ai_rewrite(T, call=lambda p: "CAUTION: the soil (RWC_eff 0.99) is close to the 1.00 limit for your "
                                            "L2 drill; drive with care. Confidence 45%.")
    assert r["source"] == "ai" and "AI-written" in r["label"]


def test_rewrite_with_a_new_number_is_rejected():
    r = explain.ai_rewrite(T, call=lambda p: "CAUTION: about 30% risk, wait 2 days.")
    assert r["source"] == "template" and "rejected" in r["note"]


def test_rewrite_that_changes_the_decision_is_rejected():
    r = explain.ai_rewrite(T, call=lambda p: "GO: the soil at 0.99 is fine.")
    assert r["source"] == "template"


def test_no_key_falls_back_to_template(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    r = explain.ai_rewrite(T)
    assert r["source"] == "template" and r["text"] == explain.template(T)
