"""Explanation text (spec 7.14): template by default; optional LLM rewrite that cannot change values or decisions.

  template(today_result)                     -> deterministic plain-language explanation
  ai_rewrite(today_result, call=None)        -> dict(text, source, label); falls back to the template when no API
                                               key is set, the call fails, or the rewrite changes a number/status.
The LLM only receives the computed values and reasons. It never decides GO / CAUTION / NO-GO and never makes a number.
Key: environment variable ANTHROPIC_API_KEY (never in the repo). Model: FIELDGO_LLM_MODEL (default below).
"""
from __future__ import annotations

import json
import os
import re
import urllib.request

DEFAULT_MODEL = "claude-haiku-5-5"
AI_LABEL = "AI-written explanation (rewrites the computed result; cannot change values or the decision)"
NUM = re.compile(r"-?\d+(?:[.,]\d+)?")


def template(t: dict) -> str:
    """Deterministic explanation from the Today result."""
    if t.get("status") not in ("GO", "CAUTION", "NO-GO"):
        return "Not available: there is no weather or soil data for this day."
    head = {"GO": "You can go", "CAUTION": "Go only with care", "NO-GO": "Do not go"}[t["status"]]
    c = t.get("conditions") or {}
    parts = [f"{head}: {t['status']} for {t.get('machine_id')} (axle-load class {t.get('load_class')}) on "
             f"{t.get('parcel_id')} on {t['date']:%d %b %Y}."]
    parts += [r if r.endswith(".") else r + "." for r in t.get("reasons", [])]
    if c:
        parts.append(f"Rain today {c['precip_mm']:.1f} mm, last 48 h {c['precip_last48h_mm']:.1f} mm; "
                     f"soil wetness index RWC_eff {c['rwc_eff']:.2f}.")
    first = t.get("days_to_first_go")
    if t["status"] != "GO":
        parts.append("First GO: " + (f"in {first} day(s)." if isinstance(first, int) else f"{first}."))
    parts.append(f"Confidence {t.get('confidence')}%: {t.get('best_next_check')}")
    return " ".join(parts)


def _numbers(text: str) -> set[str]:
    return {n.replace(",", ".").lstrip("0") or "0" for n in NUM.findall(text)}


def guard(source: str, rewrite: str, status: str) -> tuple[bool, str]:
    """The rewrite may only use numbers present in the source and must keep the decision word."""
    extra = _numbers(rewrite) - _numbers(source)
    if extra:
        return False, f"rewrite introduced numbers not in the result: {sorted(extra)[:5]}"
    others = {"GO", "CAUTION", "NO-GO"} - {status}
    if status not in rewrite or any(re.search(rf"(?<![-\w]){re.escape(o)}(?![-\w])", rewrite) for o in others
                                    if not (o == "GO" and status == "NO-GO")):
        return False, "rewrite changed or dropped the decision"
    return True, "ok"


def _call_claude(prompt: str) -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    body = json.dumps({"model": os.environ.get("FIELDGO_LLM_MODEL", DEFAULT_MODEL), "max_tokens": 300,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, method="POST", headers={
        "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        out = json.loads(r.read())
    return "".join(b.get("text", "") for b in out.get("content", []))


def ai_rewrite(t: dict, call=None) -> dict:
    src = template(t)
    prompt = ("Rewrite this field-work advice for a farmer in 2-3 short, plain sentences. Keep the decision word "
              f"({t.get('status')}) exactly. Use only numbers that appear in the text; do not add, round or change "
              "any number; do not add advice that is not in the text.\n\nText: " + src)
    try:
        text = (call or _call_claude)(prompt).strip()
    except Exception as e:                                      # no key, no network, API error -> template
        return {"text": src, "source": "template", "label": "Template explanation", "note": str(e)}
    ok, why = guard(src, text, t.get("status", ""))
    if not ok:
        return {"text": src, "source": "template", "label": "Template explanation",
                "note": f"AI text rejected: {why}"}
    return {"text": text, "source": "ai", "label": AI_LABEL, "note": ""}
