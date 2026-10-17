"""Tyre-based compaction check: a simplified Terranimo-style chain (17 Oct; PROPOSED, Mirela reviews).

Used only when the farmer enters the tyre inflation pressure. Without it the 6.8.3 table (status x axle-load class)
stays the default. All numbers come from params.COMPACTION.

  contact(wheel_load_t, inflation_bar)      -> mean ground pressure MGP = inflation + carcass, footprint area, radius
  vertical_stress(mgp, radius, depth, nu)   -> Söhne/Fröhlich stress under the centre of a uniform circular footprint:
                                               sigma_z = MGP * (1 - (z / sqrt(z^2 + a^2))^nu); nu = 3 is Boussinesq
  depth_of_stress(p, a, nu, target_kpa)     -> depth where sigma_z = target (closed form)
  concentration_factor(pF)                  -> nu: 6 soft (pF 1.7), 5 firm (2.0), 4 hard (2.7), 3 at wilting (4.2)
  pf_from_rwc(rwc_eff, sand, clay, om)      -> matric potential of the 0-30 cm layer as pF (full bucket = pF 2.0)
  strength(clay, pF, layer)                 -> precompression stress Pc: log10 Pc = log10 Pc_ref + k * clay * (pF - 2)
  classify(sci)                             -> green / yellow / red with SCI = log10(stress / strength)
  check(...)                                -> profile 0.1-0.8 m, topsoil / subsoil class, 50 kPa at 50 cm rule;
                                               the subsoil class (persistent damage) picks the 6.8.3 cost row, the
                                               topsoil class is shown (tilled topsoil is usually above its strength
                                               and is repaired by tillage, wet-dry and frost cycles: Terranimo note)
  max_wheel_load_t(...), levers(...)        -> what would help: lighter wheel load, lower tyre pressure

Simplifications (stated in the UI): uniform circular footprint (FRIDA's peak stresses under the tyre centre are higher,
so the topsoil stress is a lower bound); single wheel, no stress from the other wheels; one matric potential for
the whole profile (as Terranimo light); no bulk-density effect on strength; frozen soil not assessed.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from engine import params as prm

NA = "not available"
G = 9.81                                      # kN per tonne
CLASS_RANK = {"green": 0, "yellow": 1, "red": 2}
ORIGIN = "modelled+assumption"
LABEL = "simplified Terranimo-style check (prototype)"
SOURCES = ("Terranimo introduction note (terranimo.dk); Stettler et al. 2014, Landtechnik 69:132; "
           "Schjønning et al. 2012, Soil Use Manage.; Calleja-Huerta et al. 2023, Soil Till. Res. 233:105790")


def _c(key):
    return prm.COMPACTION[key].value


def _num(x) -> bool:
    return isinstance(x, (int, float, np.integer, np.floating)) and not pd.isna(x)


# --------------------------------------------------------------------------- tyre-soil contact
def contact(wheel_load_t, inflation_bar) -> dict | None:
    """Mean ground pressure (kPa), footprint area (m2) and equivalent circle radius (m); None if not physical."""
    if not (_num(wheel_load_t) and _num(inflation_bar)) or wheel_load_t <= 0 or inflation_bar <= 0:
        return None
    load_kn = float(wheel_load_t) * G
    mgp = float(inflation_bar) * 100.0 + _c("carcass_kpa")
    area = load_kn / mgp
    return {"load_kn": load_kn, "mgp_kpa": mgp, "area_m2": area, "radius_m": math.sqrt(area / math.pi)}


# --------------------------------------------------------------------------- stress in the profile
def vertical_stress(mgp_kpa: float, radius_m: float, depth_m: float, nu: float) -> float:
    if depth_m <= 0:
        return float(mgp_kpa)
    c = depth_m / math.sqrt(depth_m ** 2 + radius_m ** 2)
    return float(mgp_kpa) * (1.0 - c ** nu)


def depth_of_stress(p: float, a: float, nu: float, target_kpa: float) -> float:
    """Depth (m) of the target stress contour under the wheel centre; 0 if the surface pressure is below it."""
    if target_kpa >= p:
        return 0.0
    c = (1.0 - target_kpa / p) ** (1.0 / nu)
    return c * a / math.sqrt(1.0 - c * c)


def concentration_factor(pf: float) -> float:
    xs, ys = zip(*_c("nu_by_pf"))
    return float(np.interp(pf, xs, ys))


# --------------------------------------------------------------------------- soil wetness and strength
def pf_from_rwc(rwc_eff, sand_pct, clay_pct, om_pct):
    """pF of the 0-30 cm layer from the bucket state, on the Saxton & Rawls retention slope of the parcel.

    theta = WP + RWC_eff * (FC - WP); pF = fc_pf + B * log10(theta_FC / theta), B = ln(1500/33) / ln(theta33/theta1500)
    (the S&R power-law exponent), anchored so that a full bucket (RWC 1) is the bucket's field capacity
    (params SAXTON_RAWLS fc_kpa = 10 kPa -> pF 2.0, the Terranimo / European convention).
    """
    if not all(_num(v) for v in (rwc_eff, sand_pct, clay_pct, om_pct)):
        return None
    from engine.soil import field_capacity, saxton_rawls
    wp, t33 = (float(v) for v in saxton_rawls(sand_pct, clay_pct, om_pct))
    fc = float(field_capacity(sand_pct, clay_pct, om_pct))       # the bucket's FC (params SAXTON_RAWLS fc_kpa)
    if not (0 < wp < t33 <= fc):
        return None
    b = math.log(1500.0 / 33.0) / math.log(t33 / wp)
    theta = max(wp + float(rwc_eff) * (fc - wp), 1e-6)
    fc_pf = math.log10(10.0 * prm.SAXTON_RAWLS["fc_kpa"].value)     # kPa -> hPa -> pF (10 kPa = pF 2.0)
    pf = fc_pf + b * math.log10(fc / theta)
    return float(min(max(pf, _c("pf_min")), _c("pf_max")))


def strength(clay_pct: float, pf: float, layer: str) -> float:
    """Soil strength (precompression stress, kPa) from clay and pF; clay capped to the calibrated range."""
    lo, hi = _c("clay_calibrated_pct")
    clay = min(max(float(clay_pct), lo), hi)
    ref = _c("pc_ref_kpa")[layer]
    return float(10 ** (math.log10(ref) + _c("pc_clay_pf_slope") * clay * (pf - 2.0)))


def strength_from_bd(bd_g_cm3: float, clay_pct: float, pf: float) -> float:
    """Subsoil strength (kPa) from bulk density, clay and pF (Schjønning & Lamandé 2018); pF clamped to the model range."""
    m = _c("pc_bd_model")
    lo, hi = _c("pc_bd_pf_range")
    pf_c = min(max(float(pf), lo), hi)
    clay = float(clay_pct) / 100.0
    root = m["a"] + m["b"] * float(bd_g_cm3) + m["c"] * clay + m["d"] * clay * pf_c
    return float(max(max(root, 0.0) ** 2, _c("pc_bd_min_kpa")))


def classify(sci: float) -> str:
    if sci <= 0:
        return "green"
    return "yellow" if sci <= _c("sci_yellow_max") + 1e-12 else "red"


def _worst(classes) -> str:
    return max(classes, key=CLASS_RANK.get)


# --------------------------------------------------------------------------- the check
def _not_assessed(reason: str, **extra) -> dict:
    return {"assessed": False, "reason": reason, "cost_row": NA, "overall": NA, "topsoil": NA, "subsoil": NA,
            "origin": ORIGIN, "label": LABEL, "sources": SOURCES} | extra


def check(wheel_load_t, inflation_bar, clay_pct, sand_pct, om_pct, rwc_eff, tmax_c=None, subsoil_bd=None) -> dict:
    """Stress vs strength from 0.1 to 0.8 m under one wheel, today's soil wetness.

    subsoil_bd (g/cm3, optional): subsoil strength from bulk density (Schjønning & Lamandé 2018) instead of the default.
    The strength-free rule (< 50 kPa at 50 cm) is the main subsoil test: exceeded -> subsoil at least yellow.
    """
    if _num(tmax_c) and tmax_c <= prm.FROST["tmax_c"].value:
        return _not_assessed("Frozen soil: carries traffic; the stress model does not apply.")
    c = contact(wheel_load_t, inflation_bar)
    if c is None:
        return _not_assessed("Enter the tyre inflation pressure (bar) and a wheel load above 0.")
    pf = pf_from_rwc(rwc_eff, sand_pct, clay_pct, om_pct)
    if pf is None:
        return _not_assessed("Soil texture, organic matter or soil water is missing (not guessed).")
    nu = concentration_factor(pf)
    top_max = _c("topsoil_max_m")
    rows = []
    for z in _c("depths_m"):
        layer = "topsoil" if z <= top_max else "subsoil"
        s = vertical_stress(c["mgp_kpa"], c["radius_m"], z, nu)
        pc = (strength_from_bd(subsoil_bd, clay_pct, pf) if layer == "subsoil" and _num(subsoil_bd)
              else strength(clay_pct, pf, layer))
        sci = math.log10(s / pc)
        rows.append({"depth_m": z, "layer": layer, "stress_kpa": round(s, 1), "strength_kpa": round(pc, 1),
                     "sci": round(sci, 3), "class": classify(sci)})
    prof = pd.DataFrame(rows, columns=["depth_m", "layer", "stress_kpa", "strength_kpa", "sci", "class"])
    top = _worst(prof.loc[prof.layer == "topsoil", "class"])
    sub_sci = _worst(prof.loc[prof.layer == "subsoil", "class"])
    rule_kpa, rule_z = _c("rule_stress_kpa"), _c("rule_depth_m")
    s50 = vertical_stress(c["mgp_kpa"], c["radius_m"], rule_z, nu)
    d50 = depth_of_stress(c["mgp_kpa"], c["radius_m"], nu, rule_kpa)
    rule_ok = s50 <= rule_kpa
    sub = sub_sci if rule_ok else _worst((sub_sci, _c("rule_min_subsoil_class")))
    overall = _worst((top, sub))
    lo, hi = _c("clay_calibrated_pct")
    source = (f"bulk density {float(subsoil_bd):.2f} g/cm3 (Schjønning & Lamandé 2018)" if _num(subsoil_bd)
              else "default (Terranimo note, subsoil density unknown: precautionary)")
    notes = ["Uniform circular footprint: real peak stress under the tyre centre is higher (topsoil = lower bound).",
             "One soil wetness for the whole profile (as Terranimo light).",
             f"Subsoil strength: {source}."]
    if not rule_ok and sub_sci == "green":
        notes.append("Strength estimate says green, but 50 kPa at 50 cm is exceeded: subsoil shown as yellow "
                     "(the strength-free rule is the main test).")
    if not (lo <= float(clay_pct) <= hi):
        notes.append(f"Clay {float(clay_pct):.0f}% is outside the calibrated clay range {lo:.0f}-{hi:.0f}%: strength "
                     f"uses {min(max(float(clay_pct), lo), hi):.0f}% (indicative only).")
    return {"assessed": True, "wheel_load_t": float(wheel_load_t), "inflation_bar": float(inflation_bar),
            "mgp_kpa": round(c["mgp_kpa"], 1), "area_m2": round(c["area_m2"], 3), "pf": round(pf, 2),
            "nu": round(nu, 2), "profile": prof, "topsoil": top, "subsoil": sub, "overall": overall,
            "stress_50cm_kpa": round(s50, 1), "depth_50kpa_m": round(d50, 2),
            "rule_50kpa_50cm": "met" if rule_ok else "exceeded", "subsoil_sci_class": sub_sci,
            "subsoil_strength_source": source, "subsoil_bd": float(subsoil_bd) if _num(subsoil_bd) else None,
            "cost_row": _c("class_to_cost_row")[sub], "notes": notes, "origin": ORIGIN, "label": LABEL,
            "sources": SOURCES}


# --------------------------------------------------------------------------- what would help
def max_wheel_load_t(inflation_bar, clay_pct, sand_pct, om_pct, rwc_eff, layer: str = "subsoil",
                     cap_t: float = 20.0, subsoil_bd=None) -> float:
    """Largest wheel load (t, 0.01 t steps) that keeps every depth of `layer` green at this pressure and wetness."""
    def ok(load):
        r = check(load, inflation_bar, clay_pct, sand_pct, om_pct, rwc_eff, subsoil_bd=subsoil_bd)
        return r["assessed"] and r[layer] == "green"
    if not ok(0.05):
        return 0.0
    if ok(cap_t):
        return cap_t
    lo, hi = 0.05, cap_t
    while hi - lo > 0.005:
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if ok(mid) else (lo, mid)
    return math.floor(lo * 100) / 100


def levers(wheel_load_t, inflation_bar, clay_pct, sand_pct, om_pct, rwc_eff, tmax_c=None, subsoil_bd=None) -> list[dict]:
    """Terranimo's advice in numbers: lower tyre pressure (mostly topsoil), lighter wheel load (mostly subsoil)."""
    base = check(wheel_load_t, inflation_bar, clay_pct, sand_pct, om_pct, rwc_eff, tmax_c, subsoil_bd=subsoil_bd)
    if not base["assessed"] or base["overall"] == "green":
        return []
    out = []
    pmin, step = _c("min_field_bar"), _c("pressure_step_bar")
    if inflation_bar > pmin:
        cands = []
        p = round(float(inflation_bar) - step, 2)
        while p >= pmin - 1e-9:
            r = check(wheel_load_t, p, clay_pct, sand_pct, om_pct, rwc_eff, tmax_c, subsoil_bd=subsoil_bd)
            cands.append(((CLASS_RANK[r["subsoil"]], CLASS_RANK[r["topsoil"]]), -p, r))   # subsoil first
            p = round(p - step, 2)
        if cands:
            best_rank = min(c[0] for c in cands)
            _, neg_p, r = min((c for c in cands if c[0] == best_rank), key=lambda c: c[1])   # highest such pressure
            out.append({"lever": "lower tyre pressure", "inflation_bar": -neg_p, "wheel_load_t": float(wheel_load_t),
                        "topsoil": r["topsoil"], "subsoil": r["subsoil"], "overall": r["overall"],
                        "stress_50cm_kpa": r["stress_50cm_kpa"],
                        "note": "Only if your tyre's load/pressure table allows this pressure at this load and speed "
                                "(central tyre inflation makes it practical)."})
    if base["subsoil"] != "green":
        m = max_wheel_load_t(inflation_bar, clay_pct, sand_pct, om_pct, rwc_eff, subsoil_bd=subsoil_bd)
        if m < wheel_load_t:
            out.append({"lever": "lighter wheel load", "wheel_load_t": m,
                        "axle_load_t": round(m * _c("wheels_per_axle"), 2), "inflation_bar": float(inflation_bar),
                        "subsoil": "green" if m > 0 else base["subsoil"],
                        "note": ("Subsoil stays green up to this wheel load at today's wetness (part-filled hopper or "
                                 "tank, lighter machine, twin tyres or tracks)." if m > 0 else
                                 "No wheel load keeps the subsoil green at this pressure today: wait for drier soil.")})
    return out
