# IE-Iberdrola Datathon 2026 — Team Submission

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/moanv2/Iberdrola_Datathon/blob/main/SUBMISSION_MASTER.ipynb)

**Master submission notebook:** [`SUBMISSION_MASTER.ipynb`](./SUBMISSION_MASTER.ipynb) — runs Objectives 0 → 1 → 2 → BI export end-to-end in Colab.  See [`COLAB_SETUP.md`](./COLAB_SETUP.md) for the Drive upload manifest a juror needs before running.

**Mandatory datos.gob.es fork reference (§4.1):** the EV-forecast source that produces 	otal_ev_projected_2027 lives in our fork of Laboratorio-de-Datos:

https://github.com/moanv2/Laboratorio-de-Datos/blob/datathon-2026/Data%20Science/Ruta%20a%20la%20electrificaci%C3%B3n%20de%20la%20Movilidad/Codigo/Model_1.ipynb

The integer in `outputs/File_1.csv` is the direct output of that notebook.

## Folder map
- `01_forecast/`        Part 1. 1-pager pointing at the fork.
- `02_charging_network/` Objective 1. Notebooks 01-04 -> `outputs/File_2.csv`.
- `03_grid_viability/`  Objective 2. Notebooks 01-03 -> `outputs/File_3.csv`.
- `outputs/`            The three mandated CSVs (exact file names).
- `bi_visualization/`   Self-contained `map.html`.
- `report/`             Analytical Report (3-5 pages, PDF + DOCX source).
- `presentation/`       5-min Pitch PDF.
- `assumptions.md`      Structured assumptions log.
- `sources.md`          Data-source register.

## Deadline
**Wed 22 April 11:59 am**. Submit by 10:00 am for a buffer.

## Team + ownership
| Role | Owner | Folder |
|---|---|---|
| T1 Forecast / Objective 1 / Objective 2 | Diego | `01_forecast/` + fork |
| T2 Objective 2 / Dashboard | Marco | `02_charging_network/` |
| T3 Objective 3 / Report | Gloriana | `03_grid_viability/` |
| N1 Report | Michael | Project Manager |
| N2 BI + Pitch | Claudia | `report/` |
| N3 BI + Pitch | Cecile | `bi_visualization/` + `presentation/` |

## Workflow
Nob