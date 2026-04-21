"""
data_ingestion.py — Centralised raw-data acquisition for the IE-Iberdrola Datathon 2026 submission.

Purpose
-------
Replaces the previously-manual / hard-coded-path data downloads in Objective 1
(02_charging_network/) and Objective 2 (03_grid_viability/) with a single,
idempotent, Colab-compatible ingestion layer.

The module is intentionally stdlib-only (urllib.request, zipfile, pathlib,
hashlib, shutil, os, sys, time) so it works on a fresh Colab runtime without
extra `pip install` steps.

Public API
----------
- ensure_cnig_roads(root)        -> Path to rt_tramo_vial.shp
- ensure_nap_chargers(root)      -> Path to nap_chargers.xml
- ensure_grid_capacity(root)     -> Path to data/raw/grid_capacity/  (directory)
- ensure_all(root)               -> calls all three

All functions are idempotent. On a second run, each prints "[cached] ..." and
returns instantly.

Override via environment variables
----------------------------------
- IBE_CNIG_URL            : override the primary CNIG roads zip URL
- IBE_CNIG_MIRROR_URL     : fallback URL (e.g. a public Google Drive share)
- IBE_NAP_URL             : override the NAP DATEX2 XML endpoint
- IBE_NAP_CACHE_HOURS     : NAP cache TTL in hours (default 168 = 1 week)
- IBE_GRID_MIRROR_URL     : fallback URL for grid-capacity zip bundle
- IBE_DATA_ROOT           : override the repo root used for data/ path resolution

Data provenance
---------------
All source URLs and licences are cited in ./sources.md.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import sys
import time
import urllib.request
import urllib.error
import zipfile
from pathlib import Path
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
#  Source manifest — single source of truth for every raw dataset.
# ---------------------------------------------------------------------------
#  For each dataset we record:
#    - "url"           : primary download URL (direct HTTP GET)
#    - "mirror_env"    : env var that can override with a fallback URL
#    - "mirror_default": default fallback URL (empty = none)
#    - "target"        : path under repo root
#    - "kind"          : "file" (single file) or "zip" (extract)
#    - "expected_min_bytes": sanity floor for a successful download
#    - "citation"      : string for sources.md / analytical report
# ---------------------------------------------------------------------------
SOURCES: Dict[str, Dict] = {
    "cnig_roads": {
        "url_env": "IBE_CNIG_URL",
        "url_default": (
            # CNIG Centro de Descargas — Red de Transporte Viaria
            # This is the public landing page; direct-GET download typically
            # requires going through their form, so we also support a mirror.
            "https://centrodedescargas.cnig.es/CentroDescargas/descargar.do?"
            "serieId=RT_TVIARIA&formato=SHP"
        ),
        "mirror_env": "IBE_CNIG_MIRROR_URL",
        "mirror_default": "",
        "target_dir": "data/raw/cnig_roads/RT_VIARIA_CARRETERA",
        "required_files": [
            "rt_tramo_vial.shp",
            "rt_tramo_vial.dbf",
            "rt_tramo_vial.prj",
            "rt_tramo_vial.shx",
        ],
        "kind": "zip",
        "expected_min_bytes": 10 * 1024 * 1024,  # 10 MB floor on the zip
        "citation": (
            "CNIG (Centro Nacional de Información Geográfica) — Red de "
            "Transporte Viaria (RT_VIARIA_CARRETERA), April 2026 edition. "
            "https://centrodedescargas.cnig.es"
        ),
    },
    "nap_chargers": {
        "url_env": "IBE_NAP_URL",
        "url_default": (
            "https://infocar.dgt.es/datex2/v3/miterd/"
            "EnergyInfrastructureTablePublication/electrolineras.xml"
        ),
        "mirror_env": "",
        "mirror_default": "",
        "target_file": "data/raw/nap_chargers.xml",
        "kind": "file",
        "expected_min_bytes": 10 * 1024 * 1024,  # 10 MB floor
        "cache_hours_env": "IBE_NAP_CACHE_HOURS",
        "cache_hours_default": 168,  # 1 week
        "citation": (
            "DGT — National Access Point (NAP) for Traffic and Mobility, "
            "DATEX II v3 Energy Infrastructure publication, fetched "
            "April 2026. https://nap.transportes.gob.es/"
        ),
    },
    "grid_capacity": {
        "url_env": "",
        "url_default": "",  # Each DSO publishes separately; see required_files
        "mirror_env": "IBE_GRID_MIRROR_URL",
        "mirror_default": "",
        "target_dir": "data/raw/grid_capacity",
        "required_files": [
            "I-de 2026_04_01_R1-001_Demanda.xlsx",
            "Begasa 2026_04_01_R1003_demanda.xlsx",
            "e-distribucion 2026_04_01_R1026_demanda.xlsx",
            "e-distribucion 2026_04_01_R1299_demanda.xlsx",
            "Viesgo 2026_04_01_R1005_demanda.xlsx",
            "Eredes 2026_03_20_R1008_demanda.xlsx",
            "Naturgy 2026_04_01_R1-002_demanda.xlsx",
        ],
        "kind": "zip",  # expect a mirror zip containing all 7
        "expected_min_bytes": 100 * 1024,  # 100 KB floor on zip (small files)
        "citation": (
            "CNMC R1-001 / R1-002 / R1-003 / R1-005 / R1-008 / R1-026 / R1-299 "
            "distributor filings (i-DE, Naturgy, Begasa, Viesgo, Eredes, Endesa "
            "e-distribución), April 2026. Downloadable from each DSO's public "
            "capacity-of-access portal."
        ),
    },
}


# ---------------------------------------------------------------------------
#  Small utilities
# ---------------------------------------------------------------------------
def _is_colab() -> bool:
    return "google.colab" in sys.modules


def _log(msg: str) -> None:
    print(f"[ingest] {msg}", flush=True)


def _resolve_env(env_key: str, default: str) -> str:
    if env_key and env_key in os.environ and os.environ[env_key].strip():
        return os.environ[env_key].strip()
    return default


def _dir_has_all(dir_path: Path, required: List[str]) -> bool:
    if not dir_path.is_dir():
        return False
    existing = {p.name for p in dir_path.rglob("*") if p.is_file()}
    return all(name in existing for name in required)


def _find_in_tree(root_dir: Path, filename: str) -> Optional[Path]:
    """Return the first Path whose name matches filename, or None."""
    if not root_dir.is_dir():
        return None
    for p in root_dir.rglob(filename):
        return p
    return None


def _stream_download(url: str, dest: Path, expected_min_bytes: int) -> Path:
    """Download URL to dest with progress logging. Returns dest on success."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    _log(f"downloading {url}")
    _log(f"    -> {dest}")
    t0 = time.time()
    # User-Agent header to avoid occasional 403 from government servers
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (IE-Iberdrola-Datathon-2026 ingestion)"},
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        total = int(resp.headers.get("Content-Length", 0)) or None
        with open(tmp, "wb") as out:
            downloaded = 0
            last_pct = -1
            chunk = 1024 * 64
            while True:
                buf = resp.read(chunk)
                if not buf:
                    break
                out.write(buf)
                downloaded += len(buf)
                if total:
                    pct = int(downloaded * 100 / total)
                    if pct >= last_pct + 10:
                        _log(f"    ... {pct}% ({downloaded/1024/1024:.1f} MB)")
                        last_pct = pct
    size = tmp.stat().st_size
    if size < expected_min_bytes:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(
            f"download too small ({size} bytes < floor {expected_min_bytes}); "
            f"URL likely returned HTML / captcha / 404"
        )
    tmp.replace(dest)
    _log(f"done in {time.time()-t0:.1f}s, {size/1024/1024:.1f} MB -> {dest.name}")
    return dest


def _extract_zip(zip_path: Path, target_dir: Path) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    _log(f"extracting {zip_path.name} -> {target_dir}")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(target_dir)
    _log(f"extracted {len(list(target_dir.rglob('*')))} entries")


# ---------------------------------------------------------------------------
#  Public ensure_* functions
# ---------------------------------------------------------------------------
def _repo_root(root: Optional[Path] = None) -> Path:
    if root is not None:
        return Path(root).resolve()
    if "IBE_DATA_ROOT" in os.environ:
        return Path(os.environ["IBE_DATA_ROOT"]).resolve()
    # Fallback: walk up from the module's location
    here = Path(__file__).resolve().parent
    for ancestor in [here, *here.parents]:
        if (ancestor / "data").is_dir() and (ancestor / "02_charging_network").is_dir():
            return ancestor
    return here


def ensure_cnig_roads(root: Optional[Path] = None) -> Path:
    """Ensure CNIG interurban road shapefiles exist; return path to rt_tramo_vial.shp."""
    rt = _repo_root(root)
    spec = SOURCES["cnig_roads"]
    target_dir = rt / spec["target_dir"]
    required = spec["required_files"]

    # Cache check — accept either the exact target_dir, or any nested folder
    # containing the required files (handles shapefile zip layout variants).
    if _dir_has_all(target_dir, required):
        shp = _find_in_tree(target_dir, "rt_tramo_vial.shp")
        _log(f"[cached] cnig_roads OK at {shp}")
        return shp  # type: ignore[return-value]

    # Try primary URL, then mirror.
    url = _resolve_env(spec["url_env"], spec["url_default"])
    mirror = _resolve_env(spec["mirror_env"], spec["mirror_default"])
    urls_to_try = [u for u in (url, mirror) if u]

    download_dir = rt / "data" / "raw" / "_downloads"
    download_dir.mkdir(parents=True, exist_ok=True)
    zip_dest = download_dir / "cnig_roads.zip"

    last_err = None
    for candidate in urls_to_try:
        try:
            _stream_download(candidate, zip_dest, spec["expected_min_bytes"])
            break
        except Exception as e:
            _log(f"    download failed: {e}")
            last_err = e
            continue
    else:
        # No URL worked — fail loud with actionable instructions.
        raise FileNotFoundError(
            "CNIG roads shapefile is unavailable via automated download.\n"
            "Manual instructions:\n"
            "  1. Go to https://centrodedescargas.cnig.es/CentroDescargas/\n"
            "  2. Search for 'Red de Transporte Viaria' (RT_VIARIA_CARRETERA).\n"
            "  3. Download the ZIP for the whole of Spain.\n"
            "  4. Extract into: " + str(target_dir) + "\n"
            "     so that rt_tramo_vial.shp sits directly inside.\n"
            "Alternatively, upload the zip to a publicly-shared location and\n"
            "export IBE_CNIG_MIRROR_URL=<direct-download-url> before running.\n"
            f"(last error: {last_err})"
        )

    _extract_zip(zip_dest, target_dir)
    shp = _find_in_tree(target_dir, "rt_tramo_vial.shp")
    if shp is None:
        raise RuntimeError(
            f"rt_tramo_vial.shp not found after extraction under {target_dir}"
        )
    _log(f"cnig_roads ready at {shp}")
    return shp


def ensure_nap_chargers(root: Optional[Path] = None) -> Path:
    """Ensure the NAP DATEX II XML is cached locally; return its path."""
    rt = _repo_root(root)
    spec = SOURCES["nap_chargers"]
    target_file = rt / spec["target_file"]

    # Cache check with TTL
    cache_hours = int(_resolve_env(spec["cache_hours_env"], str(spec["cache_hours_default"])))
    if target_file.exists() and target_file.stat().st_size >= spec["expected_min_bytes"]:
        age_hours = (time.time() - target_file.stat().st_mtime) / 3600.0
        if age_hours < cache_hours:
            _log(
                f"[cached] nap_chargers OK at {target_file} "
                f"(age {age_hours:.1f}h < {cache_hours}h TTL)"
            )
            return target_file
        else:
            _log(f"cache expired ({age_hours:.1f}h >= {cache_hours}h), refetching")

    url = _resolve_env(spec["url_env"], spec["url_default"])
    _stream_download(url, target_file, spec["expected_min_bytes"])
    return target_file


def ensure_grid_capacity(root: Optional[Path] = None) -> Path:
    """Ensure all 7 DSO grid-capacity XLSX files exist; return the directory."""
    rt = _repo_root(root)
    spec = SOURCES["grid_capacity"]
    target_dir = rt / spec["target_dir"]
    required = spec["required_files"]

    if _dir_has_all(target_dir, required):
        _log(f"[cached] grid_capacity OK at {target_dir} ({len(required)} files)")
        return target_dir

    # ── Local vendor fallback ────────────────────────────────────────────
    # The 7 DSO R1-* capacity filings are ~850 KB in total and are
    # committed under resources/grid_capacity/ so that fresh clones work
    # with zero network. If every required file is present there, copy
    # them into data/raw/grid_capacity/ (gitignored) and return.
    vendor_dir = rt / "resources" / "grid_capacity"
    if _dir_has_all(vendor_dir, required):
        target_dir.mkdir(parents=True, exist_ok=True)
        for name in required:
            src = vendor_dir / name
            dst = target_dir / name
            if not dst.exists():
                shutil.copy2(src, dst)
        _log(
            f"[vendor] grid_capacity populated from resources/grid_capacity/ "
            f"({len(required)} files) -> {target_dir}"
        )
        return target_dir

    mirror = _resolve_env(spec["mirror_env"], spec["mirror_default"])
    if mirror:
        download_dir = rt / "data" / "raw" / "_downloads"
        download_dir.mkdir(parents=True, exist_ok=True)
        zip_dest = download_dir / "grid_capacity.zip"
        try:
            _stream_download(mirror, zip_dest, spec["expected_min_bytes"])
            _extract_zip(zip_dest, target_dir)
            if _dir_has_all(target_dir, required):
                return target_dir
        except Exception as e:
            _log(f"    mirror download failed: {e}")

    # Fall through: fail loud with actionable instructions.
    missing = [n for n in required if not (target_dir / n).exists()]
    raise FileNotFoundError(
        "Grid-capacity XLSX files are unavailable via automated download.\n"
        f"Missing from {target_dir}:\n  - " + "\n  - ".join(missing) + "\n"
        "Manual instructions:\n"
        "  1. Download the 7 DSO R1-* demand filings from:\n"
        "     - i-DE:      https://www.i-de.es/conexion-red-electrica/capacidad-de-acceso-de-consumo\n"
        "     - Endesa:    https://www.edistribucion.com/es/home/areas/Capacidad-de-acceso-a-la-red.html\n"
        "     - Viesgo:    https://www.viesgodistribucion.com/en/mapa-interactivo-de-red\n"
        "     - Begasa / Eredes / Naturgy : respective DSO capacidad-de-acceso portals.\n"
        "  2. Place all 7 .xlsx files directly inside:\n"
        f"     {target_dir}\n"
        "  3. Alternatively, zip them all into one archive and set:\n"
        "     IBE_GRID_MIRROR_URL=<direct-download-url>\n"
    )


def ensure_all(root: Optional[Path] = None) -> None:
    """Convenience: ensure every raw dataset needed by Obj 1 + Obj 2."""
    _log("=== ensure_all: starting ===")
    ensure_cnig_roads(root)
    ensure_nap_chargers(root)
    ensure_grid_capacity(root)
    _log("=== ensure_all: done ===")


# ---------------------------------------------------------------------------
#  CLI for manual sanity check
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    ensure_all()
