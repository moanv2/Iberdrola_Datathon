# EV Fleet Forecast — 2027 Projection

## Result

**total_ev_projected_2027 = 614,412**

This is the projected cumulative stock of battery-electric passenger vehicles (BEVs) on Spanish roads by December 2027. It serves as the foundational demand input for all downstream analyses (charging network optimization, grid viability).

## Where to find the code

The forecast lives in the **mandatory fork** of the datos.gob.es Laboratorio de Datos repository:

> [Model_1.ipynb — SARIMA Forecast (primary)](https://github.com/moanv2/Laboratorio-de-Datos/blob/datathon-2026/Data%20Science/Ruta%20a%20la%20electrificaci%C3%B3n%20de%20la%20Movilidad/Codigo/Model_1.ipynb)

Supporting notebooks in the same folder:

| Notebook | Purpose |
|---|---|
| `Model_0.ipynb` | Baseline reproduction of the original datos.gob.es SARIMA exercise |
| `Model_1.ipynb` | **Primary model** — improved SARIMA with train/test split and flow→stock conversion |
| `Model_2.ipynb` | Robustness check using NeuralProphet (541,623 — 7× narrower confidence intervals) |

## Methodology (Model_1)

1. **Data**: Monthly EV registration microdata from DGT (Jan 2015 – Feb 2026, 134 months). Source: Parquet files from the Laboratorio de Datos GitHub repo + DGT 2024–2026 supplements.

2. **Preprocessing**: Filter to passenger cars (`COD_TIPO=40`), confirmed registrations (`CLAVE_TRAMITE ∈ {1, 5, B}`), electric propulsion only. Aggregate to monthly counts.

3. **Train/test split**: Train on Jan 2015 – Dec 2024 (120 months), test on Jan 2025 – Feb 2026 (14 months).

4. **Model**: SARIMA(1,1,1)(2,0,1)[12] selected via `pmdarima.auto_arima` on the log-transformed series. Test MAPE: 12.44%.

5. **Flow → Stock conversion**: The model forecasts monthly *new registrations* (flow). To get the total fleet (stock), we take the cumulative sum of all historical registrations plus forecasted months through Dec 2027. No scrappage adjustment is applied (conservative assumption documented in `assumptions.md`).

6. **Result**: Cumulative EV stock at Dec 2027 = **614,412**.

## Robustness check (Model_2)

NeuralProphet with quantile regression produces 541,623 (−12% vs SARIMA). The narrower confidence intervals (CI width 4,546 vs 33,475 at Dec 2027) suggest SARIMA's upper bound may be optimistic, but the central estimate of 614,412 is used as the primary input per team consensus.

## Output files

- `File_1_total_ev_projected_2027.csv` — single-value CSV (Model_1 result)
- `File_1_total_ev_projected_2027_model2.csv` — single-value CSV (Model_2 result, for reference)

These feed into **File 1** (Global Network KPIs scorecard) in the `outputs/` folder once all objectives are complete.
