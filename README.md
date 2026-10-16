# FieldGo

One Streamlit app for an arable farmer (EU Agri-Hackathon 2026, Challenge #2):
- **Season** - will I finish autumn sowing by my deadline, do I need a contractor, what does delay cost?
- **Today** - can I go on this parcel today with this machine and load, what is the safer alternative, what does waiting cost?
- **Records** - "mark as done" stores the conditions; a checker groups errors in past records into root causes.

Demo farm FARM-13525 (PL415), replay mode: historical AgERA5 weather plays the role of the forecast.
The engine is deterministic; the UI only calls engine functions. Every number carries an origin label
(`real`, `modelled`, `synthetic`, `assumption`). All parameters live in `engine/params.py`.

**Status: walking skeleton.** The pages show stub numbers (`engine/stubs.py`, red "stub" badges); real engine modules replace them one by one.

## Setup (Windows, Python 3.11+)
```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install -e .          # makes `engine` and `config` importable from anywhere
```

## Data
The organisers' dataset is **not included and must not be committed** (see `.gitignore`). Build the Parquet extracts
outside the repo and point the app at them:
```
$env:FIELDGO_DATA_DIR = "E:\fieldgo-data"      # PowerShell; folder must exist
python -m engine.data --zip "<path to all-datasets.zip>" --out $env:FIELDGO_DATA_DIR
```
The skeleton runs without `FIELDGO_DATA_DIR` (stubs only).

## Run
```
streamlit run app/main.py      # from the repo root
pytest                         # data-dependent tests are skipped when FIELDGO_DATA_DIR is not set
```

## Layout
`engine/` pure functions (contract in the build spec), `app/` Streamlit pages and `components/`, `tests/` pytest.
File ownership: see the kickoff prompt (section 3).
