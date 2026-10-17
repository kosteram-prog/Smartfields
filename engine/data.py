"""Data extraction from the organisers' archive and cached loaders (owner: Marek).

Extraction (run once, ~2 min, < 1 GB RAM; reads straight from the zip in chunks):
    python -m engine.data --zip "<path>\\all-datasets.zip" --out "<FIELDGO_DATA_DIR>"

Loaders read the Parquet extracts from the folder in FIELDGO_DATA_DIR (outside the repository):
    load_farm(holding_id), load_weather(nuts3), load_operations(table, holding_id)
They take plain hashable arguments (safe to wrap in st.cache_data) and always return copies.
"""
from __future__ import annotations

import argparse
import re
import time
import zipfile
from functools import lru_cache
from pathlib import Path

import pandas as pd

import config
from engine import soil

# What to extract (data selection, not agronomy). Spec 7.1.
WEATHER_NUTS3 = ("PL415", "PL418", "RO317")           # PL418 = Gasawy field, RO317 = Romanian field
DEMO_HOLDINGS = ("FARM-13525", "FARM-16285")          # demo farm + organic example (RecordLint R2)
OPERATION_TABLES = ("planting", "harvest", "fertilisation", "plant_protection", "irrigation")
CHUNK_ROWS = 250_000
NA_VALUES = ["\\N"]                                    # SQL NULL in the organisers' CSVs

WEATHER_KEEP = ["nuts3_id", "date", "precipitation_mm", "reference_evapotranspiration_mm",
                "temperature_min_c", "temperature_mean_c", "temperature_max_c", "wind_speed_m_s",
                "quality_flag"]
DATE_COLUMNS = ["date", "plant_date", "harvest_date", "app_date"]
ID_DTYPES = {"parcel_id": str, "holding_id": str, "nuts3_id": str, "nuts3": str}


# --------------------------------------------------------------------------- reading from the zip
def _index_zip(z: zipfile.ZipFile) -> dict[str, str]:
    """Map 'folder/file.csv' (relative to the archive root) -> member name, whatever the root folder is."""
    out = {}
    for name in z.namelist():
        m = re.search(r"(?:^|/)(weather|synthetic|combined)/([^/]+\.csv)$", name)
        if m:
            out[f"{m.group(1)}/{m.group(2)}"] = name
    return out


def _chunks(z: zipfile.ZipFile, member: str, usecols=None):
    with z.open(member) as fh:
        yield from pd.read_csv(fh, chunksize=CHUNK_ROWS, na_values=NA_VALUES, dtype=ID_DTYPES,
                               usecols=usecols, low_memory=False)


def _filtered(z, member: str, column: str, keep: set, usecols=None) -> pd.DataFrame:
    parts = [c[c[column].isin(keep)] for c in _chunks(z, member, usecols)]
    parts = [p for p in parts if len(p)]
    if parts:
        return pd.concat(parts, ignore_index=True)
    head = next(_chunks(z, member, usecols)).iloc[0:0]
    return head


def _yearly(index: dict[str, str], stem: str) -> list[tuple[int, str]]:
    """Yearly files such as synthetic/synthetic_planting_2017.csv, found by pattern (not hard-coded years)."""
    pat = re.compile(rf"^{re.escape(stem)}_(\d{{4}})\.csv$")
    found = []
    for key, member in index.items():
        m = pat.match(key)
        if m:
            found.append((int(m.group(1)), member))
    return sorted(found)


def _parse_dates(df: pd.DataFrame) -> pd.DataFrame:
    for col in DATE_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


# --------------------------------------------------------------------------- extraction
def extract(zip_path, out_dir) -> dict[str, int]:
    """Read the archive in chunks, write the small Parquet extracts to out_dir, return {name: rows}."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    summary: dict[str, int] = {}

    def save(name: str, df: pd.DataFrame) -> None:
        df = _parse_dates(df.reset_index(drop=True))
        df.to_parquet(out / f"{name}.parquet", index=False)
        summary[name] = len(df)

    with zipfile.ZipFile(zip_path) as z:
        index = _index_zip(z)
        if not any(k.startswith("synthetic/") for k in index):
            raise ValueError(f"{zip_path} does not look like the organisers' archive (no synthetic/ folder).")

        # 1. weather: 10 yearly files, keep three regions
        wx_parts = []
        for _, member in _yearly(index, "weather/weather_daily"):
            wx_parts.append(_filtered(z, member, "nuts3_id", set(WEATHER_NUTS3),
                                      usecols=lambda c: c in WEATHER_KEEP))
        wx = pd.concat(wx_parts, ignore_index=True) if wx_parts else pd.DataFrame(columns=WEATHER_KEEP)
        save("wx", wx.sort_values(["nuts3_id", "date"]) if len(wx) else wx)

        # 2. holding, parcels + soil of the demo holdings
        holding = _filtered(z, index["synthetic/synthetic_holding.csv"], "holding_id", set(DEMO_HOLDINGS))
        save("holding", holding)
        parcels = _filtered(z, index["synthetic/synthetic_parcel.csv"], "holding_id", set(DEMO_HOLDINGS))
        parcel_ids = set(parcels.parcel_id)
        soil = _filtered(z, index["synthetic/synthetic_soil.csv"], "parcel_id", parcel_ids)
        merged = parcels.merge(soil, on="parcel_id", how="left")
        merged = merged.merge(holding[["holding_id", "nuts3", "organic", "uaa_ha"]], on="holding_id", how="left")
        save("parcels", merged)

        # 3. operations of the demo parcels, all years (never all 10.7 M rows at once)
        for table in OPERATION_TABLES:
            parts = [_filtered(z, member, "parcel_id", parcel_ids)
                     for _, member in _yearly(index, f"synthetic/synthetic_{table}")]
            save(table, pd.concat([p for p in parts if len(p)] or parts[:1] or [pd.DataFrame()], ignore_index=True))

        # 4. prices (all rows, small) and labour (demo holdings)
        save("prices", pd.read_csv(z.open(index["synthetic/synthetic_market_price.csv"]), na_values=NA_VALUES))
        save("labour", _filtered(z, index["combined/combined_labour_summary.csv"], "holding_id", set(DEMO_HOLDINGS)))
    return summary


# --------------------------------------------------------------------------- cached loaders
@lru_cache(maxsize=32)
def _read(path: str, mtime_ns: int) -> pd.DataFrame:
    return pd.read_parquet(path)


def _table(name: str) -> pd.DataFrame:
    path = config.get_data_dir() / f"{name}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"{path} not found. Run: python -m engine.data --zip <all-datasets.zip> --out <FIELDGO_DATA_DIR>")
    return _read(str(path), path.stat().st_mtime_ns).copy()


def load_weather(nuts3: str = "PL415") -> pd.DataFrame:
    """Daily AgERA5 weather of one region (origin: real). Regional average, not field-level."""
    wx = _table("wx")
    wx = wx[wx.nuts3_id == nuts3]
    if wx.empty:
        raise ValueError(f"No weather for region '{nuts3}'. Available: {', '.join(WEATHER_NUTS3)}")
    wx = wx.rename(columns={"precipitation_mm": "precip_mm", "reference_evapotranspiration_mm": "et0_mm",
                            "temperature_min_c": "tmin_c", "temperature_mean_c": "tmean_c",
                            "temperature_max_c": "tmax_c", "wind_speed_m_s": "wind_m_s"})
    wx = wx.sort_values("date").reset_index(drop=True)
    wx["origin"] = "real"
    return wx[["date", "precip_mm", "et0_mm", "tmin_c", "tmean_c", "tmax_c", "wind_m_s", "origin"]]


def load_farm(holding_id: str = "FARM-13525") -> pd.DataFrame:
    """Parcels of one holding with parcel soil (origin: synthetic).

    fc_mm / wp_mm come from Saxton-Rawls (engine.soil, 0-30 cm); priority is 'not available' (NaN, never 0)
    until engine.season fills it.
    """
    p = _table("parcels")
    p = p[p.holding_id == holding_id]
    if p.empty:
        raise ValueError(f"Holding '{holding_id}' not in the extract (demo holdings: {', '.join(DEMO_HOLDINGS)}).")
    out = pd.DataFrame({
        "parcel_id": p.parcel_id, "holding_id": p.holding_id, "crop": p.crop_current,
        "crop_previous": p.crop_previous, "area_ha": p.area_ha, "clay_pct": p.clay_pct, "sand_pct": p.sand_pct,
        "silt_pct": p.silt_pct, "om_pct": p.organic_matter_pct, "bulk_density_kg_dm3": p.bulk_density_kg_dm3,
        "fc_mm": float("nan"), "wp_mm": float("nan"), "priority": float("nan"),
        "nuts3": p.nuts3, "organic": p.organic, "origin": "synthetic"})
    out = soil.add_hydraulics(out)
    return out.sort_values("parcel_id").reset_index(drop=True)


def load_operations(table: str, holding_id: str = "FARM-13525") -> pd.DataFrame:
    """Operation records (planting, harvest, fertilisation, plant_protection, irrigation) of one holding."""
    if table not in OPERATION_TABLES:
        raise ValueError(f"Unknown table '{table}'. Choose one of: {', '.join(OPERATION_TABLES)}")
    ids = set(load_farm(holding_id).parcel_id)
    df = _table(table)
    return df[df.parcel_id.isin(ids)].reset_index(drop=True)


# --------------------------------------------------------------------------- sanity report + CLI
def sanity_report(out_dir) -> list[tuple[bool, str]]:
    """Checks from the pre-event test (spec 7.1 / 10). Returns [(ok, message)]."""
    checks = []
    p = pd.read_parquet(Path(out_dir) / "parcels.parquet")
    demo = p[p.holding_id == "FARM-13525"]
    checks.append((len(demo) == 51, f"FARM-13525 parcels: {len(demo)} (expected 51), {demo.area_ha.sum():.1f} ha (expected 307.9)"))
    for crop, n, ha in (("BARL", 12, 78.2), ("COWT", 9, 55.6)):
        d = demo[demo.crop_current == crop]
        checks.append((len(d) == n and abs(d.area_ha.sum() - ha) < 0.15,
                       f"{crop}: {len(d)} parcels, {d.area_ha.sum():.1f} ha (expected {n}, {ha})"))
    wx = pd.read_parquet(Path(out_dir) / "wx.parquet")
    for n3 in WEATHER_NUTS3:
        d = wx[wx.nuts3_id == n3]
        checks.append((len(d) == 3653, f"weather {n3}: {len(d)} days {d.date.min():%Y-%m-%d}..{d.date.max():%Y-%m-%d} (expected 3653)"))
    org = p[p.holding_id == "FARM-16285"]
    checks.append((len(org) > 0 and (org.organic == 1).all(), f"FARM-16285: {len(org)} parcels, organic={sorted(set(org.organic))}"))
    return checks


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Extract the FieldGo data from the organisers' archive.")
    ap.add_argument("--zip", required=True, help="path to all-datasets.zip")
    ap.add_argument("--out", default=None, help=f"output folder (default: ${config.ENV_VAR})")
    args = ap.parse_args(argv)
    out = args.out or __import__("os").environ.get(config.ENV_VAR)
    if not out:
        ap.error(f"--out or the environment variable {config.ENV_VAR} is required")
    t0 = time.time()
    summary = extract(args.zip, out)
    print(f"\nExtracted in {time.time() - t0:.0f} s to {out}")
    for name, n in summary.items():
        size = (Path(out) / f"{name}.parquet").stat().st_size / 1024
        print(f"  {name:18s} {n:>8,d} rows  {size:8.0f} KB")
    print("\nSanity check")
    ok_all = True
    for ok, msg in sanity_report(out):
        ok_all &= ok
        print(f"  [{'OK' if ok else 'CHECK'}] {msg}")
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())


def farm_summary(holding_id: str = "FARM-13525") -> dict:
    """Headline numbers for the Farm page (origin: synthetic)."""
    farm = load_farm(holding_id)
    h = _table("holding")
    h = h[h.holding_id == holding_id]
    lab = _table("labour")
    lab = lab[lab.holding_id == holding_id]
    crops = farm.groupby("crop").agg(parcels=("parcel_id", "count"), ha=("area_ha", "sum")).round(1)
    return {"holding_id": holding_id, "nuts3": farm.nuts3.iloc[0], "parcels": int(len(farm)),
            "uaa_ha": float(h.uaa_ha.iloc[0]) if len(h) else round(float(farm.area_ha.sum()), 1),
            "awu": float(lab.static_labour_awu.iloc[0]) if len(lab) else "not available",
            "organic": bool(int(farm.organic.iloc[0])),
            "crops": {c: {"parcels": int(r.parcels), "ha": float(r.ha)} for c, r in crops.iterrows()},
            "winter_cereals_ha": round(float(farm[farm.crop.isin(["BARL", "COWT"])].area_ha.sum()), 1),
            "origin": "synthetic"}
