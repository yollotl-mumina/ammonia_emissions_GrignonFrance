# Data

## `raw/`
Consolidated event databases (single row per fertilization event).
- `DB_plain_clean.xlsx` — full dataset, 152 events (2018–2025).
- `DB_first_rotation.xlsx` — 87 events (2018 to 1 Aug 2022).
- `DB_second_rotation.xlsx` — 65 events (1 Aug 2022 onwards).
- `ALFAM2_entrada_horaria.xlsx` — ALFAM2 input workbook (11 liquid organic events with hourly weather).

## `emep/`
EMEP Tier 2 outputs. Each subdirectory contains:
- `events_emep.csv` — one row per event with modelled NH₃-N.
- `summary_by_system.csv` — totals and intensity per cropping system.
- `summary_by_category.csv` — totals per product category.
- `summary_baseline_vs_corrected.csv` — sensitivity to the four toggleable corrections.

Subdirectories: `full_inventory/` (152 events), `first_rotation/` (87 events), `second_rotation/` (65 events).

## `alfam2/`
- `ALFAM2_first_rotation.xlsx` / `ALFAM2_second_rotation.xlsx` — per-rotation ALFAM2 inputs.
- `*_alfam2_by_event.csv` — per-event summary (TAN applied, NH₃-N emitted, % of TAN).
- `*_alfam2_hourly.csv` — hourly emission trajectories over the 96-h window.

## `comparison/`
Side-by-side EMEP vs ALFAM2 per-event tables used in figures.
