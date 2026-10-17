"""RecordLint-lite (owner: Marek). Spec 7.13: checks on the farm's historical records, grouped into root causes.

Rules (thresholds in params.LINT / CLOSED_PERIOD_DEFAULT / FROST):
  R1 spray dated before sowing or after harvest of the same campaign
  R2 organic holding with mineral fertiliser (R2-fert) or herbicides (R2-herb)
  R3 N fertiliser in the closed period (default 1 Dec - 31 Jan) or on frozen soil (Tmax <= 0 °C)
  R4 fertigation on a parcel that was not irrigated that year
  R5 identical N and P in every row of a parcel-year with >= 2 rows (ambiguity: annual rate repeated?)
  R6 spray on a day with heavy rain or strong wind (severity 'check', not an error)

  lint(tables, weather, holding, campaign) -> dict (pure)
  lint_records(holding_id, campaign)       -> dict (contract; loads the extracts)
"""
from __future__ import annotations

import pandas as pd

from engine import params as prm

ORIGIN = "synthetic"
FLAG_COLS = ["rule", "record_type", "record_id", "parcel_id", "year", "date", "detail"]

CARDS = {
    "R5": dict(severity="issue", title="Fertiliser rows repeat the same rate",
               why="Every row of these plot-years has identical N and P: either a copy error or an annual rate "
                   "written once per application. Totals per plot are doubtful.",
               fix="Record the rate of each application (kg/ha per pass), or one row with the annual total."),
    "R4": dict(severity="issue", title="Fertigation on plots that were not irrigated",
               why="Fertigation needs irrigation water; the irrigation record says the plot was not irrigated.",
               fix="Correct the method (e.g. broadcast) or add the missing irrigation record."),
    "R3": dict(severity="issue", title="Nitrogen in the closed period or on frozen soil",
               why="Nitrate rules forbid N in the winter closed period (default 1 Dec - 31 Jan, verify per country) "
                   "and on frozen soil; inspectors check this first.",
               fix="Check the date. If it is right, the application breaches the nitrate action programme."),
    "R1": dict(severity="issue", title="Sprays dated outside the crop's season",
               why="A spray before sowing or after harvest cannot be on this crop: wrong date, wrong plot or "
                   "wrong campaign.",
               fix="Check the date and the plot of each spray."),
    "R2-fert": dict(severity="issue", title="Mineral fertiliser on an organic holding",
                    why="Organic certification does not allow mineral (synthetic) fertiliser.",
                    fix="Check the organic status of the holding or the product type of these rows."),
    "R2-herb": dict(severity="issue", title="Herbicides on an organic holding",
                    why="Synthetic herbicides are not allowed in organic farming.",
                    fix="Check the organic status of the holding or the product of these rows."),
    "R6": dict(severity="check", title="Sprays on a rainy or windy day (check)",
               why="Heavy rain washes the product off; strong wind causes drift. Regional weather, so only a check.",
               fix="Confirm the conditions on the plot that day; note them in the record."),
}


def _in_closed_period(dates: pd.Series) -> pd.Series:
    cp = prm.CLOSED_PERIOD_DEFAULT.value
    md = dates.dt.strftime("%m-%d")
    if cp["start"] <= cp["end"]:
        return (md >= cp["start"]) & (md <= cp["end"])
    return (md >= cp["start"]) | (md <= cp["end"])       # wraps the new year (1 Dec - 31 Jan)


def _flags(df: pd.DataFrame, rule: str, rtype: str, id_col: str, date_col: str, detail) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=FLAG_COLS)
    return pd.DataFrame({"rule": rule, "record_type": rtype, "record_id": df[id_col].to_numpy(),
                         "parcel_id": df["parcel_id"].to_numpy(), "year": df["year"].to_numpy(),
                         "date": df[date_col].to_numpy(),
                         "detail": [detail(r) for r in df.itertuples()]})


def lint(tables: dict, weather: pd.DataFrame, holding: dict, campaign: int | None = None) -> dict:
    """Run R1-R6 on one holding's records. tables: planting, harvest, irrigation, fertilisation, plant_protection."""
    fert, pp = tables["fertilisation"], tables["plant_protection"]
    if campaign is not None:
        fert, pp = fert[fert["year"] == campaign], pp[pp["year"] == campaign]
    lp = prm.LINT
    wx = weather[["date", "precip_mm", "tmax_c", "wind_m_s"]]
    out = []

    # R1: sprays before sowing / after harvest of the same campaign
    if "plant_protection" in lp["r1_scope"].value and len(pp):
        x = (pp.merge(tables["planting"][["parcel_id", "year", "plant_date"]], on=["parcel_id", "year"], how="left")
               .merge(tables["harvest"][["parcel_id", "year", "harvest_date", "crop"]], on=["parcel_id", "year"], how="left"))
        bad = x[(x.app_date < x.plant_date) | (x.app_date > x.harvest_date)]
        out.append(_flags(bad, "R1", "plant_protection", "pp_id", "app_date",
                          lambda r: (f"{r.product_type.lower()} on {r.app_date:%d %b %Y}, "
                                     + (f"{(r.app_date - r.harvest_date).days} days after the {r.crop} harvest"
                                        if r.app_date > r.harvest_date else f"before sowing ({r.plant_date:%d %b %Y})"))))

    # R2: organic holding
    if int(holding.get("organic", 0) or 0) == 1:
        mf = fert[fert.product_type == "MINERAL"]
        out.append(_flags(mf, "R2-fert", "fertilisation", "fertilisation_id", "app_date",
                          lambda r: f"mineral fertiliser {r.n_kg_ha:.0f} kg N/ha on {r.app_date:%d %b %Y}"))
        hb = pp[pp.product_type.isin(lp["r2_ppp_types"].value)]
        out.append(_flags(hb, "R2-herb", "plant_protection", "pp_id", "app_date",
                          lambda r: f"{r.product_type.lower()} {r.product_name} on {r.app_date:%d %b %Y}"))

    # R3: N in the closed period or on frozen soil
    nn = fert[fert.n_kg_ha > 0].merge(wx, left_on="app_date", right_on="date", how="left")
    closed, frozen = _in_closed_period(nn.app_date), nn.tmax_c <= prm.FROST["tmax_c"].value
    out.append(_flags(nn[closed | frozen], "R3", "fertilisation", "fertilisation_id", "app_date",
                      lambda r: f"{r.n_kg_ha:.0f} kg N/ha on {r.app_date:%d %b %Y}"
                                + (f" (frozen soil, Tmax {r.tmax_c:.1f} °C)" if r.tmax_c <= prm.FROST["tmax_c"].value
                                   else " (closed period)")))

    # R4: fertigation without irrigation that year
    fg = fert[fert.method == "FERTIGATION"].merge(tables["irrigation"][["parcel_id", "year", "irrigated"]],
                                                  on=["parcel_id", "year"], how="left")
    out.append(_flags(fg[fg.irrigated.fillna(0) == 0], "R4", "fertilisation", "fertilisation_id", "app_date",
                      lambda r: f"fertigation on {r.app_date:%d %b %Y}, plot not irrigated in {r.year}"))

    # R5: identical N/P in all rows of a multi-row parcel-year
    g = fert.groupby(["parcel_id", "year"])
    same = g["n_kg_ha"].transform("nunique").eq(1) & g["p2o5_kg_ha"].transform("nunique").eq(1)
    multi = g["n_kg_ha"].transform("size").ge(2)
    r5 = fert[same & multi]
    n_rows = r5.groupby(["parcel_id", "year"]).size()
    out.append(_flags(r5, "R5", "fertilisation", "fertilisation_id", "app_date",
                      lambda r: f"{n_rows[(r.parcel_id, r.year)]} rows with {r.n_kg_ha:.1f} kg N + "
                                f"{r.p2o5_kg_ha:.1f} kg P2O5/ha"))

    # R6: spray on a rainy or windy day (check)
    s = pp.merge(wx, left_on="app_date", right_on="date", how="left")
    wet, windy = s.precip_mm >= lp["r6_rain_mm"].value, s.wind_m_s >= lp["r6_wind_m_s"].value
    out.append(_flags(s[wet | windy], "R6", "plant_protection", "pp_id", "app_date",
                      lambda r: f"{r.product_type.lower()} on {r.app_date:%d %b %Y}: rain {r.precip_mm:.1f} mm, "
                                f"wind {r.wind_m_s:.1f} m/s (regional)"))

    flags = pd.concat([f for f in out if len(f)], ignore_index=True) if any(len(f) for f in out) \
        else pd.DataFrame(columns=FLAG_COLS)
    cards = []
    for rule, grp in flags.groupby("rule", sort=False):
        meta = CARDS[rule]
        cards.append({"rule": rule, **meta, "n_rows": int(len(grp)),
                      "n_parcels": int(grp.parcel_id.nunique()),
                      "rows": grp.drop(columns=["rule"]).sort_values(["parcel_id", "date"]).reset_index(drop=True),
                      "origin": ORIGIN})
    cards.sort(key=lambda c: (c["severity"] != "issue", -c["n_rows"]))
    return {
        "holding_id": holding.get("holding_id"), "campaign": campaign,
        "n_records": int(len(fert) + len(pp)), "n_flags": int(len(flags)),
        "n_records_flagged": int(flags[["record_type", "record_id"]].drop_duplicates().shape[0]),
        "n_root_causes": sum(c["severity"] == "issue" for c in cards), "cards": cards,
        "flags": flags, "origin": ORIGIN,
    }


def lint_records(holding_id: str = "FARM-13525", campaign: int | None = None) -> dict:
    """Contract function: RecordLint on one holding's records (campaign None = all 2017-2026)."""
    from engine import data
    farm = data.load_farm(holding_id)
    tables = {t: data.load_operations(t, holding_id)
              for t in ("planting", "harvest", "irrigation", "fertilisation", "plant_protection")}
    holding = {"holding_id": holding_id, "organic": int(farm.organic.iloc[0])}
    return lint(tables, data.load_weather(farm.nuts3.iloc[0]), holding, campaign)


# --------------------------------------------------------------------------- B6: operations on NO-GO days
OP_TABLES = {"planting": ("planting_id", "plant_date", "sowing"), "fertilisation": ("fertilisation_id", "app_date", "fertilising"),
             "plant_protection": ("pp_id", "app_date", "spraying"), "harvest": ("harvest_id", "harvest_date", "harvest")}


def wet_day_operations(holding_id: str = "FARM-13525", campaign: int | None = None) -> dict:
    """Run every recorded operation through FieldGo's day status (default machine per operation, params.WET_DAY_OPS).

    Separate from the R1-R6 root causes (it does not change n_flags). The synthetic operation dates are random with
    respect to weather (data quirk 5.4 #2), so this shows what FieldGo would have advised, not farmer behaviour.
    """
    from engine import data, soil, status
    farm = data.load_farm(holding_id)
    wx = data.load_weather(farm.nuts3.iloc[0])
    sw = soil.soil_water(farm, wx)
    rows = []
    for table, (id_col, date_col, operation) in OP_TABLES.items():
        ops = data.load_operations(table, holding_id)
        if campaign is not None:
            ops = ops[ops["year"] == campaign]
        for r in ops.itertuples():
            key = f"{table}_{r.product_type}" if table == "fertilisation" else table
            machine = prm.WET_DAY_OPS[key].value
            rows.append({"table": table, "record_id": getattr(r, id_col), "parcel_id": r.parcel_id, "year": r.year,
                         "date": getattr(r, date_col), "operation": operation, "machine_id": machine,
                         "load_class": prm.MACHINES[machine]["load_class"]})
    ops = pd.DataFrame(rows)
    if ops.empty:
        return {"n_operations": 0, "n_assessed": 0, "share_nogo": "not available", "by_operation": pd.DataFrame(),
                "rows": ops, "origin": "synthetic+real+modelled"}
    ops = ops.merge(sw, on=["parcel_id", "date"], how="left")
    out = []
    for (cls, operation), g in ops.groupby(["load_class", "operation"]):
        ok = g[g.RWC_eff.notna()]
        if len(ok):
            stt = status.status_table(ok, farm, cls, 1, operation if operation != "harvest" else "harvest")
            out.append(stt)
        miss = g[g.RWC_eff.isna()].assign(status="not available")
        if len(miss):
            out.append(miss)
    res = pd.concat(out, ignore_index=True)
    assessed = res[res.status != "not available"]
    by = (assessed.groupby("table").status.value_counts(normalize=False).unstack(fill_value=0)
          .reindex(columns=["GO", "CAUTION", "NO-GO"], fill_value=0))
    by["n"] = by.sum(axis=1)
    by["share_nogo"] = by["NO-GO"] / by["n"]
    by["machine"] = [" / ".join(sorted(assessed[assessed.table == t].machine_id.unique())) for t in by.index]
    keep = ["table", "record_id", "parcel_id", "date", "operation", "machine_id", "load_class", "status", "RWC_eff",
            "rain_today_mm"]
    return {"n_operations": int(len(res)), "n_assessed": int(len(assessed)),
            "share_nogo": float((assessed.status == "NO-GO").mean()) if len(assessed) else "not available",
            "share_caution": float((assessed.status == "CAUTION").mean()) if len(assessed) else "not available",
            "by_operation": by.reset_index(), "rows": res[keep].sort_values("date").reset_index(drop=True),
            "origin": "synthetic+real+modelled",
            "note": "Synthetic operation dates are random with respect to weather: this shows what FieldGo would "
                    "have advised, not real farmer behaviour. Machine per operation is a default assumption."}
