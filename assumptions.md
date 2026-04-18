# Assumptions

| # | Assumption | Source / Justification | Impact on output |
|---|------------|------------------------|------------------|
| 1 | EV autonomy (2027 avg): 350 km | ACEA 2024 BEV fleet stats | Drives inter-station spacing in `04_station_placement.ipynb` |
| 2 | Station spacing: 150 km on highways | ~half autonomy; industry norm for range-anxiety | Determines File 2 row count |
| 3 | Default chargers per site: 4 | 4 x 150 kW = 600 kW corridor hub | Feeds `estimated_demand_kw` (MANDATORY = n x 150 kW) |
| 4 | Grid status thresholds (MW free capacity) | Sufficient >= X MW; Moderate Y-X MW; Congested < Y MW. Values set by T3 from i-DE/Endesa/Viesgo distributions. | Drives File 2 `grid_status` and File 3 inclusion |
| 5 | Spatial-join tolerance | 5 km radius, nearest-substation | Which substation each site inherits capacity from |
| 6 | No de-registration in 2027 stock | Fleet <10 yrs old; 3%/yr sensitivity in Model_1 appendix | Central `total_ev_projected_2027 = 614,412` |
| 7 | Road-network ownership includes foral exception | Default CNIG filter `titulard == 'Administración General del Estado'` drops every AP/A/N segment in País Vasco and Navarra, because those roads are owned by the Diputaciones Forales (Álava/Bizkaia/Gipuzkoa) and the Gobierno de Navarra, not the central state. `01_load_roads.ipynb` admits non-state-owned AP/A/N segments whose geometry intersects the foral provinces' bounding box `(-3.55, 41.90, -0.70, 43.55)` in ETRS89. | Adds ~6% road-km coverage in PV + Navarra → candidate station sites along AP-1/AP-8/AP-68, A-15, N-121/N-135, and N-240 no longer silently missing from the placement universe in notebook 04. |
