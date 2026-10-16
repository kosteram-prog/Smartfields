# Credits and licences
Required by the hackathon T&C (11.4, 10.5). The repository contains **no organisers' data**.

## Datasets (used through the organisers' dataset, not redistributed)
| Dataset | Use in FieldGo | Licence / terms | Attribution |
|---|---|---|---|
| EU Agri-Hackathon 2026 dataset (DG AGRI) | Synthetic farm, parcels, parcel soil, operations, prices, labour | Participants only; no redistribution (T&C 10.3) | Data: EU Agri-Hackathon 2026 dataset, DG AGRI |
| AgERA5 (Copernicus Climate Change Service) | Daily weather 2015-2024, PL415, PL418, RO317 | Copernicus licence (free use with attribution) | Contains modified Copernicus Climate Change Service information [2026] |
| Sentinel-1 (Copernicus Data Space Ecosystem) | Pre-rendered field-zone picture of the demo field (if shown) | Copernicus free, full and open data policy | Contains modified Copernicus Sentinel data [2016] |
| GUGiK ULDK | Boundary of the real demo field (if shown) | Public service, open data | Parcel boundary: GUGiK, ULDK |
| Sentinel-2 cloudless mosaic by EOX (s2maps.eu), map tiles in the Satellite page and the HTML prototype | Background satellite map | CC BY-NC-SA 4.0 for the 2018+ mosaics (verify the year used): attribution, non-commercial | Sentinel-2 cloudless - https://s2maps.eu by EOX IT Services GmbH (Contains modified Copernicus Sentinel data) |

## Software
| Library | Licence |
|---|---|
| Python | PSF License |
| Streamlit | Apache-2.0 |
| pandas | BSD-3-Clause |
| NumPy | BSD-3-Clause |
| PyArrow | Apache-2.0 |
| Plotly | MIT |
| Leaflet 1.9.4 (HTML prototype, Satellite page; loaded from unpkg) | BSD-2-Clause |
| pytest (development) | MIT |

## Methods and parameter sources
- Saxton, K.E. & Rawls, W.J. (2006). Soil water characteristic estimates by texture and organic matter. *Soil Sci. Soc. Am. J.* 70:1569-1578 (field capacity, wilting point).
- Smedema (1979), *Neth. J. Agric. Sci.* 27:27-35; AHDB, *Assessing soil moisture for successful cultivation* (trafficability at field capacity; ball/ribbon hand test).
- IOR-PIB integrated protection methodologies for winter wheat and barley; IUNG Puławy sowing-date trials; Jończyk (1998) (optimal sowing window and loss rate).
- Håkansson et al. (axle load and yield; via Penn State Extension) - impact statement only.
- National nitrate action programmes (closed periods; default 1 Dec - 31 Jan, verify per country).
- Contractor price: kb.pl price survey (Wielkopolskie, Jan 2026); WODR Poznań.

## AI tools
| Tool | Used for |
|---|---|
| Claude (Anthropic), Cursor | Code generation, tests and debugging; data exploration; drafting text. All numbers in the app come from deterministic code and the parameter tables, reviewed by the team's agronomists. |
| Claude API (optional, in the product) | Rewrites the template explanation on the Today page in plain language when `ANTHROPIC_API_KEY` is set; receives only computed values, cannot change numbers or decisions (code check), labelled 'AI-written explanation'. |
