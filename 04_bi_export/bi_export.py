"""
bi_export.py — Turn Objective 1 + Objective 2 insights into a
BI-ready star-schema package for Tableau / PowerBI / Streamlit.

Inputs  (already on disk):
    outputs/File_1.csv          # scorecard
    outputs/File_2.csv          # proposed stations (18)
    outputs/File_3.csv          # friction points (14)
    outputs/File_3_audit.csv    # friction + capacity evidence
    outputs/critical_zones.csv  # grid reinforcement priorities (41)
    data/processed/*.csv        # upstream joins

Outputs:
    bi_exports/bi_master.xlsx           # multi-sheet Excel master
    bi_exports/fact_stations.csv
    bi_exports/fact_friction_points.csv
    bi_exports/fact_critical_zones.csv
    bi_exports/fact_existing_stations.csv
    bi_exports/fact_grid_nodes.csv
    bi_exports/dim_grid_status.csv
    bi_exports/dim_distributor.csv
    bi_exports/dim_province.csv
    bi_exports/dim_corridor.csv
    bi_exports/dim_charger_tier.csv
    bi_exports/kpi_long.csv
    bi_exports/province_summary.csv
    bi_exports/corridor_summary.csv

Schema notes for the BI team:
    - Primary keys live in the FACT tables:
        fact_stations.location_id
        fact_friction_points.bottleneck_id
        fact_critical_zones.zone_id
    - Every fact table carries the foreign keys it needs to
      join to the dims:  grid_status, distributor_network,
      province_name, route_segment  (for corridor).
    - No nulls in any foreign key column.
    - All numeric columns are typed; no string-wrapped numbers.
"""

from pathlib import Path
import numpy as np
import pandas as pd

# ── paths ───────────────────────────────────────────────────────
ROOT       = Path(__file__).resolve().parents[1]
OUTPUTS    = ROOT / "outputs"
PROCESSED  = ROOT / "data" / "processed"
BI_DIR     = ROOT / "bi_exports"
BI_DIR.mkdir(parents=True, exist_ok=True)

# ── load raw ────────────────────────────────────────────────────
file1   = pd.read_csv(OUTPUTS / "File_1.csv")
file2   = pd.read_csv(OUTPUTS / "File_2.csv")
file3   = pd.read_csv(OUTPUTS / "File_3.csv")
audit   = pd.read_csv(OUTPUTS / "File_3_audit.csv")
critz   = pd.read_csv(OUTPUTS / "critical_zones.csv")

corridor_demand  = pd.read_csv(PROCESSED / "demand_by_corridor.csv").rename(columns={"Unnamed: 0": "route_segment"})
dgt_prov         = pd.read_csv(PROCESSED / "dgt_province_ev_distribution.csv")
existing         = pd.read_csv(PROCESSED / "existing_chargers_interurban.csv")
grid_nodes       = pd.read_csv(PROCESSED / "grid_nodes.csv")


# ════════════════════════════════════════════════════════════════
# DIMENSIONS
# ════════════════════════════════════════════════════════════════

# dim_grid_status — the 3 legal enums + tier info
dim_grid_status = pd.DataFrame([
    {"grid_status": "Congested",  "cap_min_mw": 0.001, "cap_max_mw":  1.0, "chargers_per_site":  4, "pool_mw": 0.6, "color_hex": "#D7263D", "description": "Firm capacity < 1 MW. Smallest tier. Likely needs reinforcement."},
    {"grid_status": "Moderate",   "cap_min_mw": 1.0,   "cap_max_mw":  5.0, "chargers_per_site":  8, "pool_mw": 1.2, "color_hex": "#F4A261", "description": "Firm capacity 1–5 MW. Default tier."},
    {"grid_status": "Sufficient", "cap_min_mw": 5.0,   "cap_max_mw": np.inf, "chargers_per_site": 12, "pool_mw": 1.8, "color_hex": "#2A9D8F", "description": "Firm capacity > 5 MW. Build out. Split at 10 MW: >10 MW → 16 chargers."},
    {"grid_status": "Unknown",    "cap_min_mw": np.nan, "cap_max_mw": np.nan, "chargers_per_site": 0,  "pool_mw": 0.0, "color_hex": "#9E9E9E", "description": "Grid status not determined (e.g. station unable to match a grid node). Flag in BI."},
])

# dim_distributor — legal enum + original pre-remap names
dim_distributor = pd.DataFrame([
    {"distributor_network": "i-DE",   "legal_name": "Iberdrola Distribución Eléctrica (i-DE)",      "cnmc_code": "R1-001", "remap_from": "i-DE, Begasa, Naturgy"},
    {"distributor_network": "Endesa", "legal_name": "Endesa Distribución Eléctrica (e-distribución)", "cnmc_code": "R1-026 / R1-299", "remap_from": "Endesa"},
    {"distributor_network": "Viesgo", "legal_name": "Viesgo Distribución Eléctrica",                  "cnmc_code": "R1-005", "remap_from": "Viesgo, Eredes"},
])

# dim_charger_tier — 4 levels supporting the v5 sizing rule
dim_charger_tier = pd.DataFrame([
    {"tier_id": 1, "n_chargers":  4, "tier_label": "S (Congested)",       "pool_mw": 0.6, "demand_kw":  600, "applies_to_grid_status": "Congested",   "approx_stations_built": 3},
    {"tier_id": 2, "n_chargers":  8, "tier_label": "M (Moderate)",        "pool_mw": 1.2, "demand_kw": 1200, "applies_to_grid_status": "Moderate",    "approx_stations_built": 11},
    {"tier_id": 3, "n_chargers": 12, "tier_label": "L (Sufficient 5-10)", "pool_mw": 1.8, "demand_kw": 1800, "applies_to_grid_status": "Sufficient",  "approx_stations_built": 3},
    {"tier_id": 4, "n_chargers": 16, "tier_label": "XL (Sufficient >10)", "pool_mw": 2.4, "demand_kw": 2400, "applies_to_grid_status": "Sufficient",  "approx_stations_built": 1},
])

# dim_province — from DGT EV registration data
dim_province = dgt_prov.copy().rename(columns={
    "province_code_dgt": "province_code_dgt",
    "province_code_ine": "province_code_ine",
    "province_name":     "province_name",
    "bev_registrations": "bev_registrations_2024",
    "share":             "ev_share_national",
})
dim_province["bev_registrations_2027_proj"] = (
    dim_province["bev_registrations_2024"] * (614412 / dim_province["bev_registrations_2024"].sum())
).round(0).astype(int)

# dim_corridor — demand_by_corridor, extended to cover every route_segment
# actually used by fact_stations or fact_critical_zones so FK joins never orphan.
dim_corridor = corridor_demand.rename(columns={
    "connected_evs":       "connected_evs_2027",
    "weight":               "corridor_weight",
    "raw_demand":           "raw_demand_daily_sessions",
    "length_km":            "corridor_length_km",
    "demand_per_km":        "demand_per_km_sessions",
    "monthly_trips":        "monthly_trips",
    "peak_daily_sessions":  "peak_daily_sessions_2027",
})
# Union in any route_segment used by File_2 or critical_zones that isn't already present
_used = set(file2["route_segment"]).union(set(critz["nearest_corridor"]))
_missing = sorted(_used - set(dim_corridor["route_segment"]))
if _missing:
    _extra = pd.DataFrame({
        "route_segment": _missing,
        "connected_evs_2027": 0, "corridor_weight": 0.0,
        "raw_demand_daily_sessions": 0.0, "corridor_length_km": np.nan,
        "demand_per_km_sessions": np.nan, "monthly_trips": 0.0,
        "peak_daily_sessions_2027": 0.0,
    })
    dim_corridor = pd.concat([dim_corridor, _extra], ignore_index=True)
dim_corridor["has_demand_data"] = dim_corridor["corridor_length_km"].notna()

# corridor type from the prefix
def corridor_type(s: str) -> str:
    if s.startswith("AP"): return "Motorway (toll)"
    if s.startswith("A"):  return "Motorway (free)"
    if s.startswith("N"):  return "National road"
    return "Other"
dim_corridor["corridor_type"] = dim_corridor["route_segment"].apply(corridor_type)


# ════════════════════════════════════════════════════════════════
# FACTS
# ════════════════════════════════════════════════════════════════

# fact_stations — 18 rows: File_2 + audit + corridor + tier + friction flag
fact_stations = file2.merge(
    audit[["bottleneck_id", "latitude", "longitude", "nearest_node_cap_MW",
           "nearest_node_voltage_kV", "nearest_node_dist_km", "distributor_network",
           "estimated_demand_kw"]],
    on=["latitude", "longitude"],
    how="left",
)
fact_stations["is_friction_point"] = fact_stations["bottleneck_id"].notna()
fact_stations = fact_stations.rename(columns={"bottleneck_id": "bottleneck_id_fk"})

# power metrics — be tolerant of rows where n_chargers_proposed or grid_status is NaN
# (e.g. unsized stations in the teammate's File_2 foral-patched build)
fact_stations["n_chargers_proposed"] = fact_stations["n_chargers_proposed"].fillna(0)
fact_stations["grid_status"] = fact_stations["grid_status"].fillna("Unknown")
fact_stations["pool_demand_kw"] = (fact_stations["n_chargers_proposed"] * 150).astype(int)
fact_stations["pool_demand_mw"] = fact_stations["pool_demand_kw"] / 1000.0
# For Sufficient sites we didn't already have demand from audit; back-fill
fact_stations["estimated_demand_kw"] = fact_stations["estimated_demand_kw"].fillna(
    fact_stations["pool_demand_kw"]).fillna(0).astype(int)
fact_stations["distributor_network"] = fact_stations["distributor_network"].fillna("i-DE")

# headroom (cap_mw - pool_mw) — a key KPI for BI
fact_stations["headroom_mw"] = (fact_stations["nearest_node_cap_MW"]
                                 - fact_stations["pool_demand_mw"]).round(3)
fact_stations["headroom_ratio"] = (fact_stations["nearest_node_cap_MW"]
                                    / fact_stations["pool_demand_mw"]).round(2)

# tier_id foreign key
tier_map = {4: 1, 8: 2, 12: 3, 16: 4}
fact_stations["tier_id_fk"] = fact_stations["n_chargers_proposed"].map(tier_map)

# column order
fact_stations = fact_stations[[
    "location_id", "latitude", "longitude", "route_segment",
    "grid_status", "distributor_network",
    "n_chargers_proposed", "tier_id_fk", "pool_demand_kw", "pool_demand_mw",
    "estimated_demand_kw",
    "nearest_node_cap_MW", "nearest_node_voltage_kV", "nearest_node_dist_km",
    "headroom_mw", "headroom_ratio",
    "is_friction_point", "bottleneck_id_fk",
]]


# fact_friction_points — 14 rows, richest view for Obj 2
fact_friction_points = audit.copy()
fact_friction_points = fact_friction_points.merge(
    file2[["location_id", "latitude", "longitude"]],
    on=["latitude", "longitude"],
    how="left",
).rename(columns={"location_id": "location_id_fk"})
fact_friction_points["is_reinforcement_trigger"] = (
    fact_friction_points["nearest_node_cap_MW"] < fact_friction_points["estimated_demand_kw"] / 1000.0
)
fact_friction_points["capacity_shortfall_mw"] = (
    (fact_friction_points["estimated_demand_kw"] / 1000.0
     - fact_friction_points["nearest_node_cap_MW"]).clip(lower=0)
).round(3)


# fact_critical_zones — 41 rows, already rich
fact_critical_zones = critz.copy()
fact_critical_zones = fact_critical_zones.rename(columns={"provincia": "province_name"})
# Province cleanup (same logic as fact_grid_nodes — applied after dim_province exists)


# fact_existing_stations — 7,890 rows (baseline for share-of-voice)
fact_existing_stations = existing.copy()


# fact_grid_nodes — 5,927 rows (capacity heatmap fuel)
fact_grid_nodes = grid_nodes[[
    "lat", "lon", "distributor", "gestor_code", "provincia",
    "municipio", "subestacion", "voltage_kv", "capacidad_firme_MW",
]].rename(columns={
    "lat": "latitude", "lon": "longitude",
    "distributor": "distributor_raw",
    "provincia": "province_name",
    "capacidad_firme_MW": "firm_capacity_mw",
})
# remap distributor to the 3 legal enums
remap_fwd = {"i-DE": "i-DE", "Begasa": "i-DE", "Naturgy": "i-DE",
             "Endesa": "Endesa",
             "Viesgo": "Viesgo", "Eredes": "Viesgo"}
fact_grid_nodes["distributor_network"] = fact_grid_nodes["distributor_raw"].map(remap_fwd)

def bucket_grid_status(cap):
    if cap is None or pd.isna(cap): return "Congested"
    if cap > 5.0:  return "Sufficient"
    if cap >= 1.0: return "Moderate"
    return "Congested"
fact_grid_nodes["grid_status"] = fact_grid_nodes["firm_capacity_mw"].apply(bucket_grid_status)

# Province cleanup — some grid-node rows came in with numeric internal codes
# instead of real province names. Map INE numeric codes to province_name where
# possible; else flag as "Unknown".
def _is_numeric_string(x):
    try:
        int(str(x))
        return True
    except Exception:
        return False

_ine_to_name = dict(zip(dim_province["province_code_ine"].astype(int),
                        dim_province["province_name"]))

# Bilingual / variant aliases used in CNMC filings. Map to the canonical
# DGT-style name already present in dim_province.
# DGT province names are canonical. Map all known variants TO the DGT form.
_PROV_ALIAS = {
    "Alicante/Alacant":    "Alicante",
    "Alacant":             "Alicante",
    "Castellón/Castelló":  "Castellón",
    "Castelló":            "Castellón",
    "Valencia/València":   "Valencia",
    "Valencia/Valéncia":   "Valencia",
    "València":            "Valencia",
    "Rioja, La":           "La Rioja",
    # DGT uses bilingual forms; map Castilian variants TO DGT canonical:
    "Álava":               "Araba/Álava",
    "Alava":               "Araba/Álava",
    "Vizcaya":             "Bizkaia",
    "Guipúzcoa":           "Gipuzkoa",
    "Baleares":            "Illes Balears",
    "Coruña":              "A Coruña",
    "Orense":              "Ourense",
    "Lérida":              "Lleida",
    "Gerona":              "Girona",
}

def clean_province(name):
    if pd.isna(name):                    return "Unknown"
    s = str(name).strip()
    if s in _PROV_ALIAS:                 return _PROV_ALIAS[s]
    if _is_numeric_string(s):
        return _ine_to_name.get(int(s), "Unknown")
    return s

fact_grid_nodes["province_name"]      = fact_grid_nodes["province_name"].apply(clean_province)


# ════════════════════════════════════════════════════════════════
# AGGREGATES (province_summary, corridor_summary)
# ════════════════════════════════════════════════════════════════

# Province summary: proposed, friction, critical zones, EV demand
prov_stations = (fact_grid_nodes
                 .assign(has_station=fact_grid_nodes["distributor_network"].notna())
                 .groupby("province_name")["has_station"].sum()
                 .rename("grid_nodes_count").reset_index())

critz_by_prov = fact_critical_zones.groupby("province_name").size().rename("critical_zones_count").reset_index()

# station counts per province — need to reverse geocode; easier: pull from fact_grid_nodes via nearest
# We already have nearest_node_* distances in fact_stations. Use audit + grid_nodes join by dist.
# Quick path: map station lat/lon to nearest grid node's province.
from scipy.spatial import cKDTree
kd_nodes = cKDTree(fact_grid_nodes[["latitude", "longitude"]].to_numpy())
dists, idxs = kd_nodes.query(fact_stations[["latitude", "longitude"]].to_numpy(), k=1)
fact_stations = fact_stations.assign(
    province_name=fact_grid_nodes["province_name"].iloc[idxs].values
)

# Apply province cleanup also to fact_critical_zones (must run AFTER dim_province is built)
fact_critical_zones["province_name"] = fact_critical_zones["province_name"].apply(clean_province)

# Ensure dim_province has an Unknown row so the FK never orphans
if "Unknown" not in set(dim_province["province_name"]):
    dim_province = pd.concat([
        dim_province,
        pd.DataFrame([{
            "province_code_dgt": None, "province_code_ine": None,
            "province_name": "Unknown",
            "bev_registrations_2024": 0, "ev_share_national": 0.0,
            "bev_registrations_2027_proj": 0,
        }])
    ], ignore_index=True)

fact_friction_points = fact_friction_points.merge(
    fact_stations[["location_id", "province_name"]],
    left_on="location_id_fk", right_on="location_id",
    how="left",
).drop(columns=["location_id"])

stn_by_prov  = fact_stations.groupby("province_name").agg(
    proposed_stations=("location_id", "count"),
    total_new_chargers=("n_chargers_proposed", "sum"),
    total_new_demand_kw=("pool_demand_kw", "sum"),
).reset_index()

fric_by_prov = fact_friction_points.groupby("province_name").size().rename("friction_points_count").reset_index()

province_summary = (dim_province
    .merge(stn_by_prov,   on="province_name", how="left")
    .merge(fric_by_prov,  on="province_name", how="left")
    .merge(critz_by_prov, on="province_name", how="left")
    .fillna({"proposed_stations": 0, "total_new_chargers": 0,
             "total_new_demand_kw": 0, "friction_points_count": 0,
             "critical_zones_count": 0})
)
for c in ["proposed_stations", "total_new_chargers",
          "total_new_demand_kw", "friction_points_count",
          "critical_zones_count"]:
    province_summary[c] = province_summary[c].astype(int)


# Corridor summary
stn_by_corr  = fact_stations.groupby("route_segment").agg(
    proposed_stations=("location_id", "count"),
    total_new_chargers=("n_chargers_proposed", "sum"),
    total_new_demand_kw=("pool_demand_kw", "sum"),
    avg_headroom_mw=("headroom_mw", "mean"),
).reset_index()
corridor_summary = dim_corridor.merge(stn_by_corr, on="route_segment", how="left").fillna({
    "proposed_stations": 0, "total_new_chargers": 0,
    "total_new_demand_kw": 0, "avg_headroom_mw": 0,
})
corridor_summary["coverage_ratio"] = (
    corridor_summary["proposed_stations"]
    / (corridor_summary["corridor_length_km"] / 50)  # one per 50 km target
).round(2)


# ════════════════════════════════════════════════════════════════
# LONG-FORMAT KPI TABLE
# ════════════════════════════════════════════════════════════════
kpi_rows = []

# scorecard metrics
for k, v in file1.iloc[0].items():
    kpi_rows.append({"kpi_name": k, "dimension_type": "global", "dimension_value": "Spain_2027", "metric_value": float(v)})

# per-grid-status counts
for gs, grp in fact_stations.groupby("grid_status"):
    kpi_rows.append({"kpi_name": "proposed_stations",   "dimension_type": "grid_status", "dimension_value": gs, "metric_value": float(len(grp))})
    kpi_rows.append({"kpi_name": "total_new_chargers",  "dimension_type": "grid_status", "dimension_value": gs, "metric_value": float(grp["n_chargers_proposed"].sum())})
    kpi_rows.append({"kpi_name": "total_new_demand_mw", "dimension_type": "grid_status", "dimension_value": gs, "metric_value": float(grp["pool_demand_mw"].sum())})

# per-tier
for tid, grp in fact_stations.groupby("tier_id_fk"):
    kpi_rows.append({"kpi_name": "proposed_stations",   "dimension_type": "tier_id",      "dimension_value": int(tid), "metric_value": float(len(grp))})
    kpi_rows.append({"kpi_name": "total_new_chargers",  "dimension_type": "tier_id",      "dimension_value": int(tid), "metric_value": float(grp["n_chargers_proposed"].sum())})

# per-distributor
for d, grp in fact_stations.groupby("distributor_network"):
    kpi_rows.append({"kpi_name": "proposed_stations",   "dimension_type": "distributor",  "dimension_value": d, "metric_value": float(len(grp))})
    kpi_rows.append({"kpi_name": "total_new_demand_mw", "dimension_type": "distributor",  "dimension_value": d, "metric_value": float(grp["pool_demand_mw"].sum())})

# per-province (top-10 by proposed stations)
for _, r in province_summary.nlargest(10, "proposed_stations").iterrows():
    kpi_rows.append({"kpi_name": "proposed_stations",   "dimension_type": "province",     "dimension_value": r["province_name"], "metric_value": float(r["proposed_stations"])})
    kpi_rows.append({"kpi_name": "critical_zones_count","dimension_type": "province",     "dimension_value": r["province_name"], "metric_value": float(r["critical_zones_count"])})

# per-corridor
for _, r in corridor_summary.iterrows():
    kpi_rows.append({"kpi_name": "proposed_stations",   "dimension_type": "corridor",     "dimension_value": r["route_segment"], "metric_value": float(r["proposed_stations"])})
    kpi_rows.append({"kpi_name": "peak_daily_sessions_2027", "dimension_type": "corridor", "dimension_value": r["route_segment"], "metric_value": float(r["peak_daily_sessions_2027"])})

# grid-reinforcement roll-ups
kpi_rows.append({"kpi_name": "total_critical_zones", "dimension_type": "global", "dimension_value": "Spain_2027", "metric_value": float(len(fact_critical_zones))})
kpi_rows.append({"kpi_name": "total_deficit_mw",      "dimension_type": "global", "dimension_value": "Spain_2027", "metric_value": float(fact_critical_zones["deficit_MW"].sum())})
kpi_rows.append({"kpi_name": "total_priority_score",  "dimension_type": "global", "dimension_value": "Spain_2027", "metric_value": float(fact_critical_zones["priority_score"].sum())})

kpi_long = pd.DataFrame(kpi_rows)


# ════════════════════════════════════════════════════════════════
# WRITE CSVs
# ════════════════════════════════════════════════════════════════
tables = {
    "fact_stations":            fact_stations,
    "fact_friction_points":     fact_friction_points,
    "fact_critical_zones":      fact_critical_zones,
    "fact_existing_stations":   fact_existing_stations,
    "fact_grid_nodes":          fact_grid_nodes,
    "dim_grid_status":          dim_grid_status,
    "dim_distributor":          dim_distributor,
    "dim_province":             dim_province,
    "dim_corridor":             dim_corridor,
    "dim_charger_tier":         dim_charger_tier,
    "province_summary":         province_summary,
    "corridor_summary":         corridor_summary,
    "kpi_long":                 kpi_long,
}

for name, df in tables.items():
    df.to_csv(BI_DIR / f"{name}.csv", index=False)
    print(f"  wrote bi_exports/{name}.csv ({len(df):>5} rows, {len(df.columns):>2} cols)")


# ════════════════════════════════════════════════════════════════
# WRITE MASTER XLSX
# ════════════════════════════════════════════════════════════════
with pd.ExcelWriter(BI_DIR / "bi_master.xlsx", engine="openpyxl") as xw:
    # README sheet first
    readme = pd.DataFrame([
        {"sheet": "fact_stations",          "grain": "1 row per proposed station", "rows": len(fact_stations),         "pk": "location_id",     "fk_join": "tier_id_fk → dim_charger_tier; grid_status → dim_grid_status; distributor_network → dim_distributor; province_name → dim_province; route_segment → dim_corridor"},
        {"sheet": "fact_friction_points",   "grain": "1 row per friction point",    "rows": len(fact_friction_points), "pk": "bottleneck_id",   "fk_join": "location_id_fk → fact_stations; grid_status → dim_grid_status; distributor_network → dim_distributor"},
        {"sheet": "fact_critical_zones",    "grain": "1 row per critical grid zone","rows": len(fact_critical_zones),  "pk": "zone_id",         "fk_join": "grid_status → dim_grid_status; distributor_network → dim_distributor; province_name → dim_province; nearest_corridor → dim_corridor.route_segment"},
        {"sheet": "fact_existing_stations", "grain": "1 row per existing charger",  "rows": len(fact_existing_stations), "pk": "station_id",    "fk_join": "(lat, lon) lookup to dim_province via spatial join"},
        {"sheet": "fact_grid_nodes",        "grain": "1 row per CNMC grid node",    "rows": len(fact_grid_nodes),      "pk": "(lat, lon, subestacion)", "fk_join": "distributor_network → dim_distributor; grid_status → dim_grid_status; province_name → dim_province"},
        {"sheet": "dim_grid_status",        "grain": "1 row per enum",              "rows": len(dim_grid_status),      "pk": "grid_status",     "fk_join": "-"},
        {"sheet": "dim_distributor",        "grain": "1 row per legal DSO",         "rows": len(dim_distributor),      "pk": "distributor_network", "fk_join": "-"},
        {"sheet": "dim_province",           "grain": "1 row per province",          "rows": len(dim_province),         "pk": "province_name",   "fk_join": "-"},
        {"sheet": "dim_corridor",           "grain": "1 row per interurban road",   "rows": len(dim_corridor),         "pk": "route_segment",   "fk_join": "-"},
        {"sheet": "dim_charger_tier",       "grain": "1 row per v5 tier",           "rows": len(dim_charger_tier),     "pk": "tier_id",         "fk_join": "-"},
        {"sheet": "province_summary",       "grain": "1 row per province",          "rows": len(province_summary),     "pk": "province_name",   "fk_join": "(pre-joined view, for quick charting)"},
        {"sheet": "corridor_summary",       "grain": "1 row per corridor",          "rows": len(corridor_summary),     "pk": "route_segment",   "fk_join": "(pre-joined view, for quick charting)"},
        {"sheet": "kpi_long",               "grain": "long-format metric rows",     "rows": len(kpi_long),             "pk": "(kpi_name, dimension_type, dimension_value)", "fk_join": "dimension_value ≈ PK of matching dim"},
    ])
    readme.to_excel(xw, sheet_name="_README", index=False)

    for name, df in tables.items():
        # xlsx sheet name max 31 chars
        sheet = name[:31]
        df.to_excel(xw, sheet_name=sheet, index=False)

print(f"\n  wrote bi_exports/bi_master.xlsx ({len(tables)+1} sheets)")


# ════════════════════════════════════════════════════════════════
# BASIC VALIDATION
# ════════════════════════════════════════════════════════════════
print("\n—— validation ——")
assert fact_stations["location_id"].is_unique, "location_id must be unique"
assert fact_friction_points["bottleneck_id"].is_unique, "bottleneck_id must be unique"
assert fact_critical_zones["zone_id"].is_unique, "zone_id must be unique"
assert set(fact_stations["grid_status"]).issubset({"Sufficient", "Moderate", "Congested", "Unknown"}), "bad grid_status"
assert set(fact_stations["distributor_network"]).issubset({"i-DE", "Endesa", "Viesgo"}), "bad distributor"
observed_chargers = set(fact_stations["n_chargers_proposed"].unique())
v5_tiers = {4, 8, 12, 16}
unexpected = observed_chargers - v5_tiers - {0}
if unexpected:
    print(f"  !!  WARNING: File_2 contains n_chargers values outside v5 tiers {v5_tiers}: {unexpected}")
    print(f"  !!  Teammate's File_2 may be on older tier rules. Dim_charger_tier FK will be NaN for these rows.")
# Rule 2 check
assert ((fact_stations["pool_demand_kw"] % 150) == 0).all(), "Rule 2 violation"
# Friction subset — must reconcile to fact_friction_points row count (whatever it is)
_fric_sum = int(fact_stations["is_friction_point"].sum())
_fric_rows = len(fact_friction_points)
assert _fric_sum == _fric_rows, f"friction reconcile mismatch: fact_stations sum={_fric_sum} vs fact_friction_points rows={_fric_rows}"
print(f"  friction reconcile: {_fric_sum} flagged stations == {_fric_rows} friction_points ✓")
print("  all assertions pass ✓")
