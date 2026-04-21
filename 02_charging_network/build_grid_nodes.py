"""
Build unified grid-node database from 7 CNMC R1-001-family distributor files.

- Handle European decimal comma (i-DE) vs dot (others)
- Determine UTM CRS per distributor (EPSG:25830 mainland, 25829 NW Galicia, 25828 Canarias)
- Coerce voltage and capacity to numeric (strings, footnote markers, nan-strings all tolerated)
- Input  : ../data/raw/grid_capacity/*.xlsx  (7 distributor files)
- Output : ../data/processed/grid_nodes.csv
    columns: distributor, gestor_code, provincia, municipio, subestacion,
             voltage_kv, capacidad_firme_MW, utm_x, utm_y, utm_crs_epsg,
             lat, lon, source_file

Run (from inside 02_charging_network/):
    python build_grid_nodes.py
"""
import pandas as pd
import numpy as np
from pathlib import Path

HERE = Path(__file__).resolve().parent

# ── Source: DSO grid-capacity XLSX bundle (centralised ingestion) ──
# Ensures all 7 R1-* filings are present before the build logic runs.
import sys as _sys
_sys.path.insert(0, str(HERE.parent))
from data_ingestion import ensure_grid_capacity  # noqa: E402
ensure_grid_capacity(HERE.parent)

RAW_DIR = HERE.parent / "data" / "raw" / "grid_capacity"
OUT_DIR = HERE.parent / "data" / "processed"
OUT_DIR.mkdir(parents=True, exist_ok=True)

FILES = [
    ("i-DE",     "I-de 2026_04_01_R1-001_Demanda.xlsx",          "Datos",                        25830),
    ("Begasa",   "Begasa 2026_04_01_R1003_demanda.xlsx",         "R1-003",                       25829),
    ("Endesa",   "e-distribucion 2026_04_01_R1026_demanda.xlsx", 0,                              25830),
    ("Endesa",   "e-distribucion 2026_04_01_R1299_demanda.xlsx", 0,                              25830),
    ("Viesgo",   "Viesgo 2026_04_01_R1005_demanda.xlsx",         "R1-005",                       25830),
    ("Eredes",   "Eredes 2026_03_20_R1008_demanda.xlsx",         "Hoja1",                        25830),
    ("Naturgy",  "Naturgy 2026_04_01_R1-002_demanda.xlsx",       "2026_04_01_R1-002_demanda",    25830),
]


def find_col(df, *keys):
    for key in keys:
        key_l = key.lower().replace(" ", "").replace("ó","o").replace("í","i").replace("á","a").replace("é","e")
        for c in df.columns:
            cl = (str(c).lower().replace(" ", "").replace("ó","o").replace("í","i")
                      .replace("á","a").replace("é","e").replace("[1]","").replace("[2]","")
                      .replace("[3]","").replace("[4]",""))
            if key_l in cl:
                return c
    return None


def to_num_eu(s):
    if s is None: return np.nan
    if isinstance(s, (int, float, np.integer, np.floating)):
        return float(s) if pd.notna(s) else np.nan
    t = str(s).strip().replace("\xa0", "")
    for mk in ("[1]", "[2]", "[3]", "[4]", "*"):
        t = t.replace(mk, "")
    t = t.strip()
    if t in ("", "nan", "NaN", "None", "-"):
        return np.nan
    if "," in t and "." not in t:
        t = t.replace(",", ".")
    elif "," in t and "." in t:
        t = t.replace(".", "").replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return np.nan


def main():
    frames = []
    for dist_name, fn, sheet, epsg in FILES:
        path = RAW_DIR / fn
        if not path.exists():
            print(f"  MISSING: {path}")
            continue
        df = pd.read_excel(path, sheet_name=sheet)
        c_gestor = find_col(df, "Gestor de red")
        c_prov   = find_col(df, "Provincia")
        c_muni   = find_col(df, "Municipio")
        c_utmx   = find_col(df, "Coordenada UTM X", "UTM X")
        c_utmy   = find_col(df, "Coordenada UTM Y", "UTM Y")
        c_sub    = find_col(df, "Subestacion")
        c_volt   = find_col(df, "Nivel de Tension", "Nivel de tension")
        c_cap    = find_col(df, "Capacidad firme disponible")

        out = pd.DataFrame({
            "distributor":        dist_name,
            "gestor_code":        df[c_gestor].astype(str) if c_gestor else "",
            "provincia":          df[c_prov].astype(str) if c_prov else "",
            "municipio":          df[c_muni].astype(str) if c_muni else "",
            "subestacion":        df[c_sub].astype(str) if c_sub else "",
            "voltage_kv":         df[c_volt].apply(to_num_eu) if c_volt else np.nan,
            "capacidad_firme_MW": df[c_cap].apply(to_num_eu) if c_cap else np.nan,
            "utm_x":              df[c_utmx].apply(to_num_eu) if c_utmx else np.nan,
            "utm_y":              df[c_utmy].apply(to_num_eu) if c_utmy else np.nan,
            "utm_crs_epsg":       epsg,
            "source_file":        fn,
        })
        frames.append(out)
        print(f"[{dist_name}] rows={len(df)}  valid-coords={out[['utm_x','utm_y']].dropna().shape[0]}")

    grid = pd.concat(frames, ignore_index=True)
    grid = grid.dropna(subset=["utm_x", "utm_y", "voltage_kv", "capacidad_firme_MW"]).reset_index(drop=True)

    try:
        from pyproj import Transformer
    except ImportError:
        import subprocess, sys
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--break-system-packages", "-q", "pyproj"])
        from pyproj import Transformer

    lats = np.full(len(grid), np.nan); lons = np.full(len(grid), np.nan)
    for epsg, idx in grid.groupby("utm_crs_epsg").groups.items():
        tf = Transformer.from_crs(f"EPSG:{int(epsg)}", "EPSG:4326", always_xy=True)
        lon, lat = tf.transform(grid.loc[idx, "utm_x"].values, grid.loc[idx, "utm_y"].values)
        lats[idx] = lat; lons[idx] = lon
    grid["lat"] = lats; grid["lon"] = lons

    mask_spain = (grid["lat"].between(27, 44)) & (grid["lon"].between(-19, 5))
    grid = grid[mask_spain].reset_index(drop=True)

    out_path = OUT_DIR / "grid_nodes.csv"
    grid.to_csv(out_path, index=False, encoding="utf-8")
    print(f"\nSaved {len(grid)} nodes -> {out_path}")
    print(f"  Congested (<1 MW):  {(grid['capacidad_firme_MW'] < 1).sum():>6}")
    print(f"  Moderate  (1-5 MW): {((grid['capacidad_firme_MW']>=1) & (grid['capacidad_firme_MW']<=5)).sum():>6}")
    print(f"  Sufficient(>5 MW):  {(grid['capacidad_firme_MW'] > 5).sum():>6}")


if __name__ == "__main__":
    main()
