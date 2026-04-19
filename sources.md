# Data Sources

All raw-data acquisition is automated via `data_ingestion.py` at the repo root.
See `DATA_INGESTION.md` for the mechanics. This table lists the authoritative
origin URL, licence, and fetch date for every external dataset consumed by
Objective 1 (Charging Network Optimization) and Objective 2 (Grid Viability
Analysis).

## Primary (automated ingestion)

| Name | URL | Type | Used for | Access date | Licence |
|------|-----|------|----------|-------------|---------|
| CNIG — Red de Transporte Viaria | https://centrodedescargas.cnig.es/CentroDescargas/ (product **RT_VIARIA_CARRETERA**) | Shapefile bundle | Obj 1 — interurban road filter (File 2) | 2026-04 | CNIG open data (CC-BY 4.0 compatible) |
| DGT NAP — Charging points (DATEX II v3) | https://infocar.dgt.es/datex2/v3/miterd/EnergyInfrastructureTablePublication/electrolineras.xml | XML live feed | Obj 1 — existing-charger baseline | 2026-04 | datos.gob.es Aviso Legal |
| i-DE (R1-001) — consumption capacity map | https://www.i-de.es/conexion-red-electrica/capacidad-de-acceso-de-consumo | XLSX | Obj 2 — grid status (File 3) | 2026-04-01 | DSO regulatory filing (public) |
| Endesa / e-distribución (R1-026, R1-299) | https://www.edistribucion.com/es/home/areas/Capacidad-de-acceso-a-la-red.html | XLSX (2 files) | Obj 2 — grid status (File 3) | 2026-04-01 | DSO regulatory filing (public) |
| Viesgo (R1-005) — interactive grid map | https://www.viesgodistribucion.com/en/mapa-interactivo-de-red | XLSX | Obj 2 — grid status (File 3) | 2026-04-01 | DSO regulatory filing (public) |
| Begasa (R1-003) — capacity filing | Begasa portal (Galicia) | XLSX | Obj 2 — grid status (File 3) | 2026-04-01 | DSO regulatory filing (public) |
| Eredes (R1-008) — capacity filing | Eredes portal (Asturias) | XLSX | Obj 2 — grid status (File 3) | 2026-03-20 | DSO regulatory filing (public) |
| Naturgy (R1-002) — capacity filing | Naturgy capacidad-de-acceso portal | XLSX | Obj 2 — grid status (File 3) | 2026-04-01 | DSO regulatory filing (public) |

## Static baselines (committed, not auto-downloaded)

| File | Origin | Notes |
|------|--------|-------|
| `data/processed/dgt_province_ev_distribution.csv` | Derived from DGT monthly parquet microdata (Obj 0 forecast fork, datos.gob.es mandatory GitHub fork) | 52 provinces x BEV registrations (2024) + projected 2027. Committed to git as a static input. |
| `resources/grid_capacity/*.xlsx` (7 files, ~850 KB) | Direct download from each DSO portal listed in the primary table above (i-DE, Endesa, Viesgo, Begasa, Eredes, Naturgy), April 2026 | Vendored copies of the public R1-* capacity filings. `ensure_grid_capacity()` copies these into `data/raw/grid_capacity/` on first run so fresh clones work with zero network. |

## Obj 0 (forecast) — out of scope for this ingestion module

The DGT monthly vehicle-registrations microdata (`data/raw/parquet/*.parquet`, 134 files) is consumed by the mandatory datos.gob.es GitHub fork referenced in the datathon brief §4.1.3. That fork lives at `01_forecast/` and produces `total_ev_projected_2027` for File_1 independently of the Obj 1 + Obj 2 pipeline. It is therefore not covered by `data_ingestion.py`.

Direct URL pattern for monthly parquet:

    https://www.dgt.es/microdatos/salida/{YYYY}/{M}/vehiculos/matriculaciones/export_mensual_mat_{YYYYMM}.zip

Licence: datos.gob.es Aviso Legal.

## Override env vars (see `data_ingestion.py`)

| Variable | Purpose |
|----------|---------|
| `IBE_DATA_ROOT` | Override the repo-root path (otherwise auto-detected). |
| `IBE_CNIG_URL` | Override the CNIG primary download URL. |
| `IBE_CNIG_MIRROR_URL` | Fallback URL for the CNIG zip (e.g. a public Google Drive share). |
| `IBE_NAP_URL` | Override the NAP DATEX II XML endpoint. |
| `IBE_NAP_CACHE_HOURS` | NAP cache TTL in hours (default 168 = 1 week). |
| `IBE_GRID_MIRROR_URL` | Fallback URL for the 7-file grid-capacity zip bundle. |
