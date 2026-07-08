#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_emep_tier2.py
=================

Compute NH3 volatilization with the EMEP/EEA Guidebook 2023 Tier 2 method on
each of the Trajectoire workbooks:

    * DB_plain_clean.xlsx     (full inventory, 2018-2025)
    * DB_first_rotation.xlsx  (rotation 1)
    * DB_second_rotation.xlsx (rotation 2, with COM/LOM relabelling)

Method (Tier 2, expressed in kg NH3-N / ha)
-------------------------------------------
    * Mineral fertilizers : NH3-N = N_total x EF_mineral(product, soil pH>7)
    * Organic products    : NH3-N = TAN     x EF_organic(product)
    * Micronutrients / additives : non-N, excluded (emission = 0)

Set CONVERT_TO_NH3 = True to also report kg NH3 / ha (factor 17/14).

Emission factors and validated corrections are carried over verbatim from the
finalized Trajectoire inventory (Resultats_NH3). They are NOT re-derived here.
The Tier 2 emission-factor values themselves come from the EMEP/EEA Guidebook
2023, chapter 3.D, for soil pH > 7 (site ~7.66) — they are NOT in the 2003
introductory chapter B1000.

Validated corrections (each is an independent toggle)
-----------------------------------------------------
    (1) ENTEC 26 NI is ammonium sulphate-nitrate (ASN), not pure AS.
        Composition-weighted EF = 0.0899 (baseline was 0.1540).
    (2) OF organic fertilizers: TAN taken from the real ammoniacal fraction of
        each datasheet (f_TAN override by event ID), not a slurry default.
    (3) Events with missing N_total but a known reference emission are recovered
        by back-calculation (N_total = emission / EF) when their EF is unchanged.

Per workbook, the script writes to <file>_EMEP/ :
    events_emep.csv          one row per event, with the recomputed emission
    summary_by_system.csv    absolute NH3-N and intensity (% of applied N)
    summary_by_category.csv  absolute NH3-N by product category
    summary_baseline_vs_corrected.csv   effect of the Entec correction

Input files are NEVER modified.

Author: Daniela Zuniga-Jimenez - AgroParisTech / UMR ECOSYS - 2026
"""

from __future__ import annotations

import argparse
import logging
import sys
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

# ─────────────────────────────────────────────────────────────────────────────
#  CONFIGURATION — edit only this block
# ─────────────────────────────────────────────────────────────────────────────

#: Workbooks to process. Override on the command line with --inputs.
DEFAULT_INPUTS: tuple[Path, ...] = (
    Path(r"C:\Users\dzuni\OneDrive\Documentos\INTERNSHIP\DB_plain_clean.xlsx"),
    Path(r"C:\Users\dzuni\OneDrive\Documentos\INTERNSHIP\Resultats_FINALES\DB_first_rotation.xlsx"),
    Path(r"C:\Users\dzuni\OneDrive\Documentos\INTERNSHIP\Resultats_FINALES\DB_second_rotation.xlsx"),
)

#: Sheet to read. None = auto-detect the sheet with the most rows.
SHEET: str | None = "Donnees_plates"

#: Correction toggles (all ON reproduces the finalized corrected inventory).
APPLY_ENTEC_ASN: bool = True         # (1) Entec EF 0.1540 -> 0.0899
APPLY_OF_DATASHEET_TAN: bool = True  # (2) override TAN of OF events by datasheet
APPLY_NTOTAL_BACKCALC: bool = True   # (3) recover missing N_total from emission
CONVERT_TO_NH3: bool = False         # also output kg NH3/ha (x 17/14)

# Emission factors — EMEP/EEA Guidebook 2023, soil pH > 7 (Grignon ~7.66).
# EF_MINERAL : kg NH3-N / kg total N applied.
# EF_ORGANIC : kg NH3-N / kg TAN applied.
EF_MINERAL: dict[str, float] = {
    "Solution azotée (UAN)": 0.1326,   # N solutions, high pH
    "Entec":                 0.0899,   # ASN (CORRECTED — baseline 0.1540)
    "Urée":                  0.1696,   # urea, high pH
    "Thiosulfate":           0.1540,   # ammonium-sulphate proxy
    "Ammonitrate":           0.0428,   # ammonium nitrate, high pH
}
#: Pre-correction mineral EFs (Entec as pure AS) — used for the baseline column.
EF_MINERAL_BASELINE: dict[str, float] = dict(EF_MINERAL, **{"Entec": 0.1540})

EF_ORGANIC: dict[str, float] = {
    "Lisier":           0.55,
    "Digestat liquide": 0.55,
    "Fumier solide":    0.68,
    "Autre organique":  0.68,
}
#: Categories that carry no ammoniacal N — excluded from the calculation.
CAT_NON_N: frozenset[str] = frozenset({"Oligo/biostimulant", "Additif"})

#: OF TAN correction: f_TAN = ammoniacal-N / total-N, per event datasheet.
#:   121 AXE-N12 (0%) ; 122 NutriBoost/Orgaliz (~5.6%) ; 123-125 LABINOR (0%).
OF_FTAN_OVERRIDE: dict[int, float] = {121: 0.000, 122: 0.056, 123: 0.000,
                                      124: 0.000, 125: 0.000}

#: Reference inventory total for DB_plain_clean (kg NH3-N/ha) — sanity check.
VALIDATION_TOTAL_FULL: float = 1125.5

logger = logging.getLogger("emep_tier2")


# ─────────────────────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def nz(x) -> float:
    """NaN-safe numeric cast: NaN/None -> 0.0.

    Avoids the ``NaN or 0`` trap (which returns NaN, not 0) that silently
    dropped events in earlier versions of the pipeline.
    """
    return 0.0 if pd.isna(x) else float(x)


def _strip_accents(text: str) -> str:
    """Return ``text`` lower-cased and without diacritics, for fuzzy matching."""
    norm = unicodedata.normalize("NFKD", str(text))
    return "".join(c for c in norm if not unicodedata.combining(c)).lower().strip()


def to_numeric_eu(series: pd.Series) -> pd.Series:
    """Coerce a column to float, tolerating French decimal commas.

    "58,5" -> 58.5. Empty cells stay NaN. Non-numeric text becomes NaN (the
    caller decides whether that is acceptable).
    """
    if series.dtype.kind in "if":
        return series.astype(float)
    text = series.astype("string").str.replace(",", ".", regex=False)
    return pd.to_numeric(text, errors="coerce")


# ─────────────────────────────────────────────────────────────────────────────
#  LOADING (auto-detects sheet and header row across the three layouts)
# ─────────────────────────────────────────────────────────────────────────────

def _detect_sheet(path: Path) -> str:
    """Return the configured sheet, or the sheet with the most rows."""
    xls = pd.ExcelFile(path)
    if SHEET is not None and SHEET in xls.sheet_names:
        return SHEET
    best, best_rows = xls.sheet_names[0], -1
    for name in xls.sheet_names:
        rows = len(pd.read_excel(path, sheet_name=name, header=None))
        if rows > best_rows:
            best, best_rows = name, rows
    return best


def _detect_header_row(path: Path, sheet: str, key: str = "ID_evenement") -> int:
    """Find the 0-indexed row holding the real header (the one with ``key``)."""
    raw = pd.read_excel(path, sheet_name=sheet, header=None, nrows=12)
    for i in range(len(raw)):
        if key in [str(x) for x in raw.iloc[i].tolist()]:
            return i
    raise ValueError(
        f"Could not locate the header row (no '{key}' cell) in "
        f"sheet '{sheet}' of {path.name}."
    )


def load_workbook_table(path: Path) -> pd.DataFrame:
    """Load one workbook into a tidy events table, layout-agnostic.

    Raises
    ------
    FileNotFoundError, ValueError
        If the file is missing, unreadable, or has no recognizable header.
    """
    if not path.is_file():
        raise FileNotFoundError(f"Input workbook not found: {path}")

    sheet = _detect_sheet(path)
    header_row = _detect_header_row(path, sheet)
    df = pd.read_excel(path, sheet_name=sheet, header=header_row)
    df = df.dropna(how="all")  # drop fully empty trailing rows, if any

    logger.info("  Loaded %d events from '%s' (sheet '%s', header row %d).",
                len(df), path.name, sheet, header_row + 1)
    return df


# ─────────────────────────────────────────────────────────────────────────────
#  CORE — EMEP Tier 2 emission per event
# ─────────────────────────────────────────────────────────────────────────────

def _event_emission(
    row: pd.Series, ef_mineral: dict[str, float]
) -> tuple[float, float, str]:
    """Compute one event's NH3-N emission (kg/ha).

    Returns
    -------
    (emission, n_applied, note) : tuple
        ``emission``  : kg NH3-N/ha (NaN if it cannot be computed).
        ``n_applied`` : total N applied for that event (kg N/ha), for intensity.
        ``note``      : short tag describing how the value was obtained.
    """
    cat = str(row["Categorie"]).strip()
    n_total = to_numeric_scalar(row.get("N_total_kgNha"))
    tan = to_numeric_scalar(row.get("TAN_kgNha"))
    ev_id = int(row["ID_evenement"]) if not pd.isna(row.get("ID_evenement")) else -1
    ref_emis = to_numeric_scalar(row.get("NH3_emis_kgNha"))

    # 1) Non-ammoniacal products: no NH3 by definition.
    if cat in CAT_NON_N:
        return 0.0, nz(n_total), "non-N (excluded)"

    # 2) Mineral fertilizers: emission = N_total x EF_mineral.
    if cat in ef_mineral:
        ef = ef_mineral[cat]
        # (3) Back-calculate a missing N_total from the reference emission.
        if pd.isna(n_total):
            if APPLY_NTOTAL_BACKCALC and not pd.isna(ref_emis) and ef > 0:
                n_total = ref_emis / ef
                return ref_emis, n_total, "N_total back-calculated"
            logger.warning("    Event %s (%s): N_total missing, cannot compute.",
                           ev_id, cat)
            return np.nan, nz(n_total), "missing N_total"
        return n_total * ef, n_total, "mineral"

    # 3) Organic products: emission = TAN x EF_organic.
    if cat in EF_ORGANIC:
        # (2) OF datasheet override: TAN = f_TAN x N_total for listed events.
        if APPLY_OF_DATASHEET_TAN and ev_id in OF_FTAN_OVERRIDE:
            tan = OF_FTAN_OVERRIDE[ev_id] * nz(n_total)
        if pd.isna(tan):
            logger.warning("    Event %s (%s): TAN missing, cannot compute.",
                           ev_id, cat)
            return np.nan, nz(n_total), "missing TAN"
        return tan * EF_ORGANIC[cat], nz(n_total), "organic"

    # 4) Unknown category: flag, do not guess an EF.
    logger.warning("    Event %s: unknown category '%s' (no EF). Skipped.",
                   ev_id, cat)
    return np.nan, nz(n_total), "unknown category"


def to_numeric_scalar(value) -> float:
    """Coerce a single cell to float, tolerating a French decimal comma."""
    if pd.isna(value):
        return np.nan
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace(",", "."))
    except ValueError:
        return np.nan


def compute_emep_tier2(df: pd.DataFrame) -> pd.DataFrame:
    """Add recomputed Tier 2 emission columns to a copy of ``df``.

    Adds:
        NH3_emis_kgNha_EMEP   recomputed emission (corrected EFs/toggles)
        N_applied_kgNha       total N applied used for the intensity ratio
        calc_note             provenance tag per event
        NH3_emis_kgNha_base   emission with the pre-correction Entec EF
        NH3_emis_kgha         (only if CONVERT_TO_NH3) emission as kg NH3/ha
    """
    out = df.copy()

    ef_corr = EF_MINERAL if APPLY_ENTEC_ASN else EF_MINERAL_BASELINE

    corrected = out.apply(lambda r: _event_emission(r, ef_corr), axis=1,
                          result_type="expand")
    out["NH3_emis_kgNha_EMEP"] = corrected[0]
    out["N_applied_kgNha"] = corrected[1]
    out["calc_note"] = corrected[2]

    # Baseline (Entec as pure AS) for the correction-effect comparison.
    baseline = out.apply(lambda r: _event_emission(r, EF_MINERAL_BASELINE)[0],
                         axis=1)
    out["NH3_emis_kgNha_base"] = baseline

    if CONVERT_TO_NH3:  # NH3-N -> NH3 mass (molar ratio 17/14)
        out["NH3_emis_kgha"] = out["NH3_emis_kgNha_EMEP"] * (17.0 / 14.0)

    return out


# ─────────────────────────────────────────────────────────────────────────────
#  SUMMARIES
# ─────────────────────────────────────────────────────────────────────────────

def summarize_by_system(df: pd.DataFrame) -> pd.DataFrame:
    """Absolute NH3-N and intensity (% of applied N) per cropping system."""
    grp = df.groupby("Systeme", dropna=False).agg(
        NH3N_kgha=("NH3_emis_kgNha_EMEP", "sum"),
        N_applied_kgha=("N_applied_kgNha", "sum"),
        n_events=("ID_evenement", "count"),
    )
    # Intensity = NH3-N volatilized / total N applied (guard against /0).
    grp["intensity_pct"] = np.where(
        grp["N_applied_kgha"] > 0,
        100.0 * grp["NH3N_kgha"] / grp["N_applied_kgha"],
        np.nan,
    )
    return grp.sort_values("NH3N_kgha", ascending=False).round(3)


def summarize_by_category(df: pd.DataFrame) -> pd.DataFrame:
    """Absolute NH3-N by product category."""
    grp = df.groupby("Categorie", dropna=False).agg(
        NH3N_kgha=("NH3_emis_kgNha_EMEP", "sum"),
        n_events=("ID_evenement", "count"),
    )
    return grp.sort_values("NH3N_kgha", ascending=False).round(3)


def summarize_baseline_vs_corrected(df: pd.DataFrame) -> pd.DataFrame:
    """Effect of the Entec ASN correction on each system's NH3-N."""
    grp = df.groupby("Systeme", dropna=False).agg(
        baseline_kgha=("NH3_emis_kgNha_base", "sum"),
        corrected_kgha=("NH3_emis_kgNha_EMEP", "sum"),
    )
    grp["delta_kgha"] = grp["corrected_kgha"] - grp["baseline_kgha"]
    return grp.round(3)


# ─────────────────────────────────────────────────────────────────────────────
#  PER-FILE DRIVER
# ─────────────────────────────────────────────────────────────────────────────

def process_file(path: Path) -> None:
    """Run the full Tier 2 calculation on one workbook and write its outputs."""
    logger.info("Processing %s", path.name)
    df = load_workbook_table(path)

    required = {"ID_evenement", "Systeme", "Categorie",
                "N_total_kgNha", "TAN_kgNha", "NH3_emis_kgNha"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{path.name}: missing required column(s) {sorted(missing)}.")

    result = compute_emep_tier2(df)

    out_dir = path.with_name(path.stem + "_EMEP")
    out_dir.mkdir(parents=True, exist_ok=True)

    result.to_csv(out_dir / "events_emep.csv", index=False)
    by_system = summarize_by_system(result)
    by_system.to_csv(out_dir / "summary_by_system.csv")
    summarize_by_category(result).to_csv(out_dir / "summary_by_category.csv")
    summarize_baseline_vs_corrected(result).to_csv(
        out_dir / "summary_baseline_vs_corrected.csv")

    total = result["NH3_emis_kgNha_EMEP"].sum()
    n_skipped = int(result["NH3_emis_kgNha_EMEP"].isna().sum())
    logger.info("  Total NH3-N: %.1f kg/ha across %d events (%d not computed).",
                total, len(result), n_skipped)

    # Sanity check only for the full inventory.
    if path.name.lower().startswith("db_plain_clean"):
        diff = abs(total - VALIDATION_TOTAL_FULL)
        flag = "OK" if diff <= 1.0 else "CHECK"
        logger.info("  Validation vs %.1f kg/ha: diff=%.2f [%s].",
                    VALIDATION_TOTAL_FULL, diff, flag)

    logger.info("  Wrote 4 CSV summaries to '%s/'.", out_dir.name)


# ─────────────────────────────────────────────────────────────────────────────
#  CLI
# ─────────────────────────────────────────────────────────────────────────────

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run EMEP/EEA Guidebook 2023 Tier 2 NH3 volatilization on "
                    "the Trajectoire workbooks.",
    )
    parser.add_argument(
        "--inputs", type=Path, nargs="+", default=list(DEFAULT_INPUTS),
        help="One or more workbooks to process (default: the three Trajectoire files).",
    )
    parser.add_argument("--verbose", action="store_true",
                        help="Enable debug-level logging.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)-8s %(message)s",
    )

    failures = 0
    for path in args.inputs:
        try:
            process_file(Path(path))
        except (FileNotFoundError, ValueError) as exc:
            logger.error("%s", exc)
            failures += 1

    if failures:
        logger.error("Finished with %d file(s) failed.", failures)
        return 1
    logger.info("All files processed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
