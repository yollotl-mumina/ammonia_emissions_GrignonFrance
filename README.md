[README.md](https://github.com/user-attachments/files/31124795/README.md)
# Ammonia emissions across the Trajectoire cropping systems (Grignon, France)

Modelling ammonia (NH₃) volatilization and indirect N₂O emissions across the seven cropping systems of the Trajectoire experimental platform, using EMEP Tier 2 and ALFAM2.

**Summer Program 2026 · Final Defense (July 2026)**
**Daniela Zúñiga-Jiménez** — UMR ECOSYS (INRAE / AgroParisTech, Université Paris-Saclay)

> The 16-slide defense deck (`report/pptx/`), the full report (`report/docx/`), and the presentation script are aligned on the same set of results and figures.

---

## Overview

The **Trajectoire** platform at Grignon (Île-de-France) compares seven cropping systems designed around contrasting sustainability objectives on a common silt-loam soil. Between the first (2018–2022) and second (2022–2025) rotations, two systems transitioned to anaerobic digestion — the control lineage became a crop-oriented methanization system (CTR→COM) and the mixed-farming lineage became a livestock-oriented one (MF→LOM).

This repository contains all data, code, figures, and the defense package needed to reproduce:

1. A complete **NH₃-N inventory** across the 152 fertilization events using EMEP Tier 2.
2. A process-based analysis of the 11 liquid organic events using **ALFAM2** (Set 3).
3. An **indirect-N₂O climate cost** derived from the EMEP inventory (IPCC 2019 methodology).

## Headline results

| Metric | Value |
|:---|:---|
| Full inventory NH₃-N (152 events) | **1,125.5 kg NH₃-N ha⁻¹** |
| Rotation 1 (87 events, 4.2 yr) | 667.2 kg NH₃-N ha⁻¹ |
| Rotation 2 (65 events, 2.8 yr) | 458.3 kg NH₃-N ha⁻¹ |
| Emission intensity R1 → R2 | 12.1% → 14.6% (**+21%**) |
| Slurry mean volatilization (ALFAM2) | 29.1% of TAN |
| Digestate mean volatilization (ALFAM2) | 63.1% of TAN (**≈ 2× slurry**) |
| Indirect N₂O (platform total) | ~4,830 kg CO₂-eq ha⁻¹ |
| Intensity change CTR → COM | +21% |
| Intensity change MF → LOM | +49% |

The absolute drop between rotations (–31%) is confounded by record length; per year, emissions rise +3%, and per kg N applied, intensity rises +21%. This is the **methanization paradox** at the heart of the analysis.

## Repository structure

```
ammonia_emissions_GrignonFrance/
├── data/
│   ├── raw/                       Source event databases (152 events; both rotations)
│   ├── emep/
│   │   ├── full_inventory/        EMEP outputs for all 152 events
│   │   ├── first_rotation/        EMEP outputs for R1 (87 events, 2018–2022)
│   │   └── second_rotation/       EMEP outputs for R2 (65 events, 2022–2025)
│   ├── alfam2/                    ALFAM2 inputs and per-event outputs
│   └── comparison/                EMEP vs ALFAM2 per-event tables
├── src/
│   └── pipeline/                  Numbered end-to-end pipeline (Python + R)
├── figures/                       All figures (PNG) used in the report and slides
├── report/
│   ├── docx/                      Full report + presentation script (DOCX)
│   └── pptx/                      Final defense deck (21 slides)
├── docs/                          Methodology notes
├── requirements.txt               Python dependencies
├── install.R                      R dependencies (ALFAM2)
├── run_all.sh                     End-to-end reproduction script
├── CITATION.cff                   Citation metadata
└── LICENSE
```

## Data

- **`data/raw/DB_plain_clean.xlsx`** — consolidated event database (152 events × 37 variables).
- **`data/raw/DB_first_rotation.xlsx`** / **`DB_second_rotation.xlsx`** — same data split at 1 August 2022.
- **`data/raw/ALFAM2_entrada_horaria.xlsx`** — ALFAM2 input workbook (11 liquid organic events, hourly weather).

All events were verified with the platform's field manager to have been applied using the same **trailing-shoe** technique (ALFAM2 code `ts`).

## Pipeline

The scripts in `src/pipeline/` run end-to-end and are numbered by step:

| # | Script | Purpose |
|---|---|---|
| 1 | `1_split_rotations.py` | Split events at 1 Aug 2022 and relabel CTR→COM, MF→LOM |
| 2 | `2_run_emep_tier2.py` | Apply EMEP/EEA 2023 Tier 2 factors to all events |
| 3 | `3_plot_emep_results.py` | Generate EMEP figures |
| 4 | `4_split_alfam2_rotations.py` | Prepare ALFAM2 inputs per rotation |
| 5 | `5_run_alfam2.R` | Run ALFAM2 (Set 3) via the official R package |
| 6 | `6_plot_alfam2_results.py` | Generate ALFAM2 figures |
| 7 | `7_compare_alfam2_emep.py` | Per-event comparison of the two models |
| 8 | `8_plot_changed_systems_comparison.py` | Focus on CTR→COM and MF→LOM transitions |
| 9 | `9_estimate_indirect_n2o.py` | Apply IPCC 2019 EF₄ × 44/28 × GWP₁₀₀ = 273 |

## Reproducibility

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Install R packages (ALFAM2)
Rscript install.R

# 3. Run the full pipeline (from repository root)
bash run_all.sh
```

## Methods (brief)

- **EMEP Tier 2** (European Environment Agency, 2023): emission = N applied × EF(product, pH). The soil pH of the platform (7.66) places emission factors in the high-pH domain of the EMEP guidebook.
- **ALFAM2 Set 3** (Hafner et al., 2019, 2025): process-oriented dynamic model with first-order transfer from TAN pools, weather-resolved at hourly resolution over a 96-h window. Applied to the 11 liquid organic events under uniform trailing-shoe placement.
- **Indirect N₂O**: not a model. The volatilized N is multiplied by the IPCC 2019 emission factor EF₄ = 0.010 (range 0.002–0.018), converted to N₂O mass (44/28), and expressed in CO₂-equivalent using GWP₁₀₀ = 273 (IPCC AR6).

## Key references (see `report/docx/Trajectoire_NH3_report_FINAL.docx` for the full list with DOIs)

- AgroParisTech (2024). *Trajectoire — Review of the first crop rotation 2017–2022*.
- European Environment Agency (2023). *EMEP/EEA air pollutant emission inventory guidebook 2023*. https://www.eea.europa.eu/publications/emep-eea-guidebook-2023
- Fangueiro, D., Hjorth, M., & Gioelli, F. (2015). Acidification of animal slurry — a review. *Journal of Environmental Management, 149*, 46–56. https://doi.org/10.1016/j.jenvman.2014.10.001
- Gu, B., et al. (2021). Abating ammonia is more cost-effective than nitrogen oxides for mitigating PM₂.₅ air pollution. *Science, 374*(6568), 758–762. https://doi.org/10.1126/science.abf8623
- Hafner, S. D., et al. (2018). The ALFAM2 database on ammonia emission from field-applied manure. *Agricultural and Forest Meteorology, 258*, 66–79. https://doi.org/10.1016/j.agrformet.2017.11.027
- Hafner, S. D., et al. (2019). A flexible semi-empirical model for estimating ammonia volatilization from field-applied slurry. *Atmospheric Environment, 199*, 474–484. https://doi.org/10.1016/j.atmosenv.2018.11.034
- Hafner, S. D., et al. (2025). Improved tools for estimation of ammonia emission from field-applied animal slurry. *Atmospheric Environment, 340*, 120910. https://doi.org/10.1016/j.atmosenv.2024.120910
- IPCC (2019). *2019 Refinement to the 2006 IPCC Guidelines for National Greenhouse Gas Inventories: Vol. 4, Ch. 11.* https://www.ipcc-nggip.iges.or.jp/public/2019rf/
- Möller, K., & Müller, T. (2012). Effects of anaerobic digestion on digestate nutrient availability and crop growth. *Engineering in Life Sciences, 12*(3), 242–257. https://doi.org/10.1002/elsc.201100085
- Sommer, S. G., & Hutchings, N. J. (2001). Ammonia emission from field applied manure and its reduction. *European Journal of Agronomy, 15*(1), 1–15. https://doi.org/10.1016/S1161-0301(01)00112-5

## Deliverables

- `report/docx/Trajectoire_NH3_report_FINAL.docx` — full report
- `report/pptx/Trajectoire_NH3_defense_FINAL.pptx` — final defense deck (16 slides)

## License

This work is released under the MIT License. See `LICENSE`.

## Contact

Daniela Zúñiga-Jiménez — Summer Program 2026, UMR ECOSYS (INRAE / AgroParisTech).
