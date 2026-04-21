# Data Ingestion

## What this is

`data_ingestion.py` at the repo root is a small, stdlib-only module that
replaces every manual "download this zip / copy these files" step that used
to be embedded in the notebooks. It is called automatically by:

- `02_charging_network/01_load_roads.ipynb` (cell 4) → `ensure_cnig_roads()`
- `02_charging_network/02_existing_chargers.ipynb` (cell 4) → `ensure_nap_chargers()`
- `02_charging_network/build_grid_nodes.py` (top of file) → `ensure_grid_capacity()`

Nothing else in the pipeline had to change. Downstream notebooks
(`03_demand_allocation`, `04_station_placement`, `03_grid_viability/01_critical_zones`,
`04_bi_export/bi_export.py`) read only from `data/processed/` or `outputs/`
and are byte-identical to the pre-ingestion version.

## What it does

For each external dataset the module:

1. Looks for the expected file(s) under `data/raw/…`.
2. If present and above a minimum-size floor, logs `[cached]` and returns the path.
3. Otherwise streams a download from a primary URL (and optionally a mirror URL)
   with 10% progress logging, extracts zips in place, then verifies expected files
   exist.
4. For the NAP DATEX II XML, it also applies a TTL (default 1 week) so repeated
   runs do not hammer the DGT server.

Failures are loud and actionable: the error message tells the user which
environment variable to set or which URL to use for a manual download.

## How the jury runs it

On a fresh Google Colab runtime:

```python
# Clone the repo
!git clone <repo> && cd <repo>

# Run any of the Obj 1 / Obj 2 notebooks. The first cell that needs raw
# data will call ensure_* and download what is missing.
```

No manual download step. Typical first-run times:

| Dataset | First-run time | Re-run (cached) |
|---------|----------------|-----------------|
| CNIG roads (zip ~300 MB subset) | ~2-4 min over home internet | <1 s |
| NAP DATEX II XML (~80 MB) | ~30-60 s | <1 s (within TTL) |
| DSO grid-capacity bundle (~850 KB of XLSX, vendored under `resources/grid_capacity/`) | <1 s (no network) | <1 s |

## Vendored datasets

The 7 DSO R1-* capacity filings (~850 KB total) are committed under
`resources/grid_capacity/` so a fresh clone can run Objective 2 with zero
network access. `ensure_grid_capacity()` copies them into
`data/raw/grid_capacity/` (gitignored) on first run. This is a pragmatic
choice — the files are small, their public origin URLs are in
`sources.md`, and each DSO's portal requires manual navigation to fetch
them, which is unfriendly for a jury re-run.

## Overrides (env vars)

See `sources.md` for the full list. The two worth remembering:

- `IBE_CNIG_MIRROR_URL` — set to a public Drive / S3 link if the CNIG primary
  URL is unreachable from the jury's network. The module falls through to it
  automatically.
- `IBE_NAP_CACHE_HOURS` — raise if the jury re-runs many times in one sitting.

## Rule compliance

This change is constrained to the *ingestion* layer. Specifically:

- Every analytical cell downstream of the ingestion cells is byte-identical
  vs. the pre-ingestion notebooks on `main`.
- Variable contracts are preserved: `shp_path` / `roads_gdf` / `resp_nap` are
  still the names the downstream code reads; only the upstream code that
  *produces* them has been centralised.
- File_1, File_2, File_3, and critical_zones.csv produced after ingestion
  changes match (within documented row-count drift from the foral-ownership
  patch) the pre-ingestion outputs. See `end_to_end_verification.log` after
  the feature/pipeline run.

## Source of truth

- Manifest: top of `data_ingestion.py` (the `SOURCES` dict).
- Public URLs + licences: `sources.md`.
- Analytical report references: cite both of the above.
