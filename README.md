# FieldGo

**Plan the season. Decide today. Keep clean records.**
A decision aid for arable farmers, built during the EU Agri-Hackathon 2026 (Challenge #2 "Connect Data for Smarter Fields").

| Page | Question it answers |
|---|---|
| **Season** | Will I finish autumn sowing by my deadline? Do I need a contractor? What does a delay cost? (10 real autumns, AgERA5 2015-2024) |
| **Today** | Can I go on this parcel today with this machine and load? What is the next 72 h? What is the N-loss risk of fertilising now? |
| **Records** | "Mark as done" stores the conditions; *Record check* groups errors in past records into a few root causes |

Demo: farm **FARM-13525** (PL415, Poznań region), **replay mode**: historical AgERA5 weather plays the role of the forecast.

## How it works
- **Deterministic engine** (`engine/`): plain functions, inputs -> DataFrame or dict. The UI (`app/`) never computes agronomy.
- **Every number carries its origin**: `real` (AgERA5 weather), `modelled` (our engine), `synthetic` (organisers' farm data), `assumption` (parameter tables). The app shows it next to each number.
- **All parameters live in `engine/params.py`**, each with value, unit, origin and source. Missing inputs show "not available", never 0.

| Module | What it does | Spec |
|---|---|---|
| `engine/data.py` | Extracts the needed rows from the organisers' zip into small Parquet files; cached loaders | 7.1 |
| `engine/soil.py` | Saxton & Rawls (2006) field capacity / wilting point; daily 0-30 cm soil-water bucket; RWC and RWC_eff | 6.3, 7.2 |
| `engine/status.py` | Day status GO / CAUTION / NO-GO per parcel, machine load class and passes | 6.4, 7.3 |
| `engine/season.py` | Season simulation: parcel priority, day-by-day allocation, P(finish by deadline), contractor recommendation, sensitivity | 7.4-7.6 |
| `engine/cost.py` | Cost of delay (late-start and weather parts), contractor value, "if you wait", "if you go now" (wet traffic, illustrative) | 6.8, 6.8.3, 7.5, 7.15 |
| `engine/today.py` | Today: field access + operation suitability, 72-h strip, confidence | 7.7, 7.9 |
| `engine/plan.py` | Safer plan (other parcel, lighter load, lighter machine, other day), each with its cost | 7.8 |
| `engine/records.py` | Records with conditions; BBCH estimate | 7.11-7.12 |
| `engine/lint.py` | RecordLint R1-R6 grouped into root causes; operations on NO-GO days | 7.13 |
| `engine/ncheck.py` | N-loss risk after fertilising (prototype) | 6.7, 7.10 |
| `engine/explain.py` | Plain-language explanation: template; optional AI rewrite that cannot change values (`ANTHROPIC_API_KEY`) | 7.14 |
| `engine/validate.py` | Model vs Sentinel-1 radar on the real Gasawy field (Oct 2016) | 8 |
| `engine/sensitivity.py` | One assumption at a time: P, 2016 finish, workable days, contractor, cost, demo statuses | 11 |
| `engine/stubs.py` | Placeholder outputs for every contract function (used until a module exists) | - |

## Run it (Windows, Python 3.10+; tested on 3.10 and 3.13)
```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install -e .                                   # makes engine/ and config importable

# data: NOT in this repository (organisers' terms). Extract once into a folder outside the repo:
$env:FIELDGO_DATA_DIR = "C:\path\to\extracts"     # must exist
python -m engine.data --zip "C:\path\to\all-datasets.zip" --out $env:FIELDGO_DATA_DIR   # ~2 min, < 1 GB RAM

streamlit run app/main.py                          # from the repository root
pytest                                             # data-dependent tests are skipped without FIELDGO_DATA_DIR
```
Without `FIELDGO_DATA_DIR` the app still opens and shows stub numbers (red "stub" badge).

## Data
The EU Agri-Hackathon 2026 dataset (DG AGRI) is **not included and must not be committed** (`.gitignore` blocks
`*.csv`, `*.parquet`, `*.zip`, `*.tif`). The extraction keeps: AgERA5 daily weather 2015-2024 for PL415, PL418, RO317;
holdings, parcels and parcel soil for FARM-13525 and the organic example FARM-16285; their operations 2017-2026;
market prices; labour. Farm, parcel and operation data are **synthetic**; weather is **real** (reanalysis, regional
average, not field-level).

## Limits (say them out loud)
- Thresholds, machine profiles and loss rates are prototype assumptions from published sources, not calibrated field
  rules. They are editable and shown with their source.
- Weather is a regional average; soil is synthetic per parcel; the soil-water model is a simple 0-30 cm bucket.
- Synthetic yields and prices do not react to weather, so euro values are illustrative and always shown as a range.

## Extra pages (Mirela — FieldGo integrations)

Added on top of Marek's kickoff skeleton (do not replace his pages):

- **Loss calculator** (`app/pages/6_Loss.py`) — go now on wet soil vs wait a day, per parcel, from the engine (`entry_cost`, `wait_cost`).
- **Satellite** (`app/pages/7_Satellite.py`) — Copernicus / Sentinel map; optional `COPERNICUS_ACCESS_TOKEN`, public EOX fallback tiles.
- **Connect** (`app/pages/8_Connect.py`) — John Deere, CLAAS, Climate FieldView, weather stations as API connection points (no live OAuth).

Parameters were **appended** only (`LOSS_CALC`, `SATELLITE`, `INTEGRATIONS`). Existing `COST` / `WET_TRAFFIC_LOSS` values were not changed.

## HTML prototype screens (review)

Alongside the Streamlit kickoff, this branch adds a static farmer-facing prototype for review:

- `index.html` — FieldGo branding, wet-soil / delay loss calculator, Copernicus/Sentinel map view, and demo API connect panel (John Deere, CLAAS, Climate FieldView, weather stations). Hooks are labelled as connect points only; no live vendor logins.
- `serve.py` — optional local static server that can inject `COPERNICUS_ACCESS_TOKEN` into `/config.js` without writing secrets to disk.
- `.env.example` — documents the optional token and port; never commit real values.

```bash
python3 serve.py
# optional: COPERNICUS_ACCESS_TOKEN=your_token python3 serve.py
```

Open http://127.0.0.1:8000. Demo JSON datasets (`farms.json`, `weather.json`) are intentionally not committed on this branch; rebuild locally if you need the full compliance/weather demo data.

## Licence and credits
Code: MIT (see `LICENSE` once added). Data sources, libraries, methods and AI tools: see [CREDITS.md](CREDITS.md).
