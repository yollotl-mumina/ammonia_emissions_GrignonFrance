#!/usr/bin/env bash
# End-to-end reproduction of the Trajectoire NH3 / indirect-N2O analysis.
# Run from the repository root:  bash run_all.sh
set -euo pipefail
cd "$(dirname "$0")"

echo "==> 1. EMEP Tier 2 inventory (full + both rotations)"
python src/pipeline/2_run_emep_tier2.py --inputs \
    data/raw/DB_plain_clean.xlsx data/raw/DB_first_rotation.xlsx data/raw/DB_second_rotation.xlsx

echo "==> 2. Indirect N2O + sensitivity (second rotation shown; change --input/--scope as needed)"
python src/analysis/sensitivity_and_indirect_n2o.py \
    --input results/emep/second_rotation/events_emep.csv \
    --outdir results/sensitivity_and_n2o --scope "second rotation (COM/LOM)"

echo "==> 3. Model-choice sensitivity + band-application counterfactual (data-driven)"
python src/analysis/alfam2_method_sensitivity.py \
    --input results/alfam2/ALFAM2_entrada_horaria_alfam2_by_event.csv \
    --outdir results/sensitivity_and_n2o --full-emep-total 1125.5 \
    --scope "full set (2018-2025)"

echo "==> 4. Real ALFAM2 re-run (reproduction + band counterfactual)"
Rscript src/analysis/alfam2_counterfactual.R

echo "==> 5. Figures"
python src/analysis/plot_emep_results_clear.py \
    --input results/emep/first_rotation/events_emep.csv --outdir figures --scope "first rotation"
python src/analysis/plot_alfam2_clear.py --outdir figures
python src/analysis/plot_rotation_comparison.py
python src/analysis/fix_figures.py

echo "==> Done. Outputs in results/ and figures/."
