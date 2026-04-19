# Colab Setup — Drive upload manifest for `SUBMISSION_MASTER.ipynb`

This document describes the one-time data staging required before a juror (or
the team) runs the master submission notebook in Google Colab.

## TL;DR

1. Upload the `data/raw/` subfolders listed below into a top-level folder named
   `IE_Iberdrola_Datathon_Data` on your Google Drive.
2. Open `SUBMISSION_MASTER.ipynb` in Colab.
3. Run all cells. The notebook mounts Drive, clones the repo, installs
   dependencies, and runs Objectives 0 → 1 → 2 → BI export end-to-end.

## Required Drive folder layout

```
/MyDrive/
└── IE_Iberdrola_Datathon_Data/
    └── data/
        └── raw/
            ├── cnig_roads/              ~2.2 GB  (CNIG interurban road shapefile bundle)
            │   ├── rt_tramo_vial.shp
            │   ├── rt_tramo_vial.shx
            │   ├── rt_tramo_vial.dbf
            │   ├── rt_tramo_vial.prj
            │   ├── rt_tramo_vial.cpg
            │   └── (any other CNIG files you have)
            ├── nap_chargers.xml         ~80 MB   (DGT NAP DATEX II charger feed)
            └── parquet/                 ~86 MB   (DGT monthly registration microdata)
                └── *.parquet
```

**Total upload:** ~2.4 GB.

## What comes from the git clone (do **not** upload)

The master notebook clones <https://github.com/moanv2/Iberdrola_Datathon> at
runtime, which provides:

- `resources/grid_capacity/*.xlsx` — 7 DSO R1-* capacity filings (~850 KB, vendored in-repo)
- `data/processed/dgt_province_ev_distribution.csv` — static baseline
- All notebooks, helper modules (`data_ingestion.py`, `build_grid_nodes.py`, `bi_export.py`)
- All past output files (`outputs/File_*.csv`, `bi_exports/*`)

## Upload tips

- **Web drag-and-drop** is fine but can take 30-60 min for the CNIG 2.2 GB bundle on a home connection.
- **Google Drive desktop sync** (Drive for Desktop) is faster and auto-handles retries — recommended.
- Preserve the folder names exactly as above. The notebook symlinks these paths
  into the cloned repo's `data/raw/` folder at runtime.

## Running the notebook

1. Go to <https://github.com/moanv2/Iberdrola_Datathon/blob/main/SUBMISSION_MASTER.ipynb>
2. Click **Open in Colab** (badge at the top of the notebook, or use the URL:
   <https://colab.research.google.com/github/moanv2/Iberdrola_Datathon/blob/main/SUBMISSION_MASTER.ipynb>)
3. Colab will load the notebook from GitHub. Click **Runtime → Run all**.
4. First-run order of events (roughly 45-60 min on a free Colab CPU runtime):
   - 0.1 Drive mount — ~30 s (browser auth popup)
   - 0.2 Git clone — ~5 s
   - 0.3 `pip install` geopandas stack — ~3 min
   - 0.4 Symlink Drive data into repo — instant
   - 0.5 Ingestion sanity check — instant (vendored grid_capacity populates)
   - 1   Obj 0 forecast constant — instant
   - 2.1 Load CNIG roads — ~2-3 min (SQL filter on 2.2 GB shapefile)
   - 2.2 Existing chargers — ~30 s
   - 2.3 Demand allocation — ~10 s
   - 2.4 Station placement — ~1 min
   - 3.5 Build grid_nodes.csv — ~30 s
   - 3.6 Critical zones — ~2 min
   - 4   BI export — ~30 s
   - 5   Summary — instant

**Note for jurors:** all cells have baked outputs from a prior execution
on the team lead's local machine (per datathon §5.1). You may scroll the
notebook top-to-bottom to evaluate the full work without re-executing.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `drive.mount('/content/drive')` fails | Re-auth the popup, then re-run cell 0.1 |
| `geopandas` fails to import after 0.3 | Restart runtime and re-run all (Colab occasionally needs a kernel restart after the geopandas install) |
| `cnig_roads/` not found after 0.4 | Verify the Drive folder name is exactly `IE_Iberdrola_Datathon_Data` and the shapefile subfolder is `data/raw/cnig_roads/` |
| `ensure_nap_chargers()` fails | Normal if Drive copy missing — it will live-fetch from the DGT NAP endpoint (needs ~30 s) |
| `build_grid_nodes.py` complains about missing XLSX | The 7 capacity files are vendored under `resources/grid_capacity/` in the repo — check the git clone completed successfully |

## Environment overrides (optional)

You can override paths with env vars if your setup differs:

| Variable | Purpose |
|---|---|
| `IBE_DATA_ROOT` | Change the repo root that `data_ingestion` walks from |
| `IBERDROLA_ROOT` | Change the repo root that `03_grid_viability/01_critical_zones.ipynb` walks from |
| `IBE_NAP_URL` | Override the DGT NAP endpoint (default is the live feed) |
| `IBE_NAP_CACHE_HOURS` | Change the NAP cache TTL (default 168 h) |
| `IBE_GRID_MIRROR_URL` | Supply a mirror zip URL for grid_capacity instead of using the vendored files |
