#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
split_rotations.py
==================

Standalone tool that splits the Trajectoire fertilization-event database
(``DB_plain_clean.xlsx``) into two derived subsets, ready for the EMEP/EEA
Guidebook Tier 2 NH3 volatilization model:

    1. First rotation  -> events sown BEFORE the second-rotation cut-off date.
    2. Second rotation -> events sown ON or AFTER the cut-off date.

Design decisions (validated against the Trajectoire brochure and the database):

* The real header of the ``Donnees_plates`` sheet is on the 4th row
  (rows 1-3 are a title and free-text notes). It is read with ``header=3``.
* ``N_total_kgNha`` ships as text because two cells use a French decimal
  comma ("58,5", "6,5"). These are repaired (comma -> dot -> float) so the
  column becomes numeric without dropping any event.
* The split is performed BY THE SOWING DATE of the second rotation. The
  brochure does not give an exact day, so the cut-off is configurable and
  defaults to 2022-08-01 (autumn 2022 -> second rotation).
* In the SECOND-rotation subset only, the systems that were physically
  replaced on the platform are relabelled: CTR -> COM (crop-oriented
  methanization) and MF -> LOM (livestock-oriented methanization).
* The full 37-column structure of the source table is preserved in each
  subset, and empty cells (legitimate missing values) are kept empty.

Usage
-----
    python split_rotations.py
    python split_rotations.py --input path/to/DB_plain_clean.xlsx \
                              --output-dir path/to/Resultats_FINALES \
                              --cut-date 2022-08-01

Author: generated for the Trajectoire NH3 modelling pipeline.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

# --------------------------------------------------------------------------- #
# Configuration (override via CLI flags)                                       #
# --------------------------------------------------------------------------- #

#: Worksheet that holds the flat event table.
SHEET_NAME: str = "Donnees_plates"

#: 0-indexed row that contains the real column names (4th row of the sheet).
HEADER_ROW: int = 3

#: Default boundary between the two rotations (sowing date of rotation 2).
#: Events with Date < CUT_DATE -> first rotation; Date >= CUT_DATE -> second.
DEFAULT_CUT_DATE: str = "2022-08-01"

#: System codes that were replaced on the platform for the second rotation.
#: Applied ONLY to the second-rotation subset.
SECOND_ROTATION_RELABEL: dict[str, str] = {
    "CTR": "COM",  # Control -> Crop-Oriented Methanization
    "MF": "LOM",   # Mixed Farming -> Livestock-Oriented Methanization
}

#: Columns required to exist for the export to be considered valid.
REQUIRED_COLUMNS: tuple[str, ...] = (
    "ID_evenement", "Systeme", "Parcelle", "Annee", "Date",
    "Product", "Categorie", "N_total_kgNha", "TAN_kgNha",
    "Methode_application", "NH3_emis_kgNha",
)

logger = logging.getLogger("split_rotations")


# --------------------------------------------------------------------------- #
# Loading & validation                                                        #
# --------------------------------------------------------------------------- #

def load_database(path: Path) -> pd.DataFrame:
    """Read the flat event table from the Excel workbook.

    Parameters
    ----------
    path : Path
        Path to ``DB_plain_clean.xlsx``.

    Returns
    -------
    pandas.DataFrame
        The raw 152-event table with its original 37 columns.

    Raises
    ------
    FileNotFoundError
        If the workbook does not exist.
    ValueError
        If the target sheet is missing or the table is empty.
    """
    if not path.is_file():
        raise FileNotFoundError(f"Input workbook not found: {path}")

    try:
        available = pd.ExcelFile(path).sheet_names
    except Exception as exc:  # noqa: BLE001 - surface any reader failure clearly
        raise ValueError(f"Could not open '{path}' as an Excel workbook: {exc}") from exc

    if SHEET_NAME not in available:
        raise ValueError(
            f"Sheet '{SHEET_NAME}' not found in {path}. "
            f"Available sheets: {available}"
        )

    df = pd.read_excel(path, sheet_name=SHEET_NAME, header=HEADER_ROW)

    if df.empty:
        raise ValueError(f"Sheet '{SHEET_NAME}' contains no data rows.")

    logger.info("Loaded %d events x %d columns from '%s'.",
                df.shape[0], df.shape[1], path.name)
    return df


def validate_database(df: pd.DataFrame) -> None:
    """Run structural sanity checks; raise on blocking problems, warn otherwise.

    Blocking conditions (raise ``ValueError``):
        * a required column is missing;
        * the ``Date`` column cannot be parsed to datetime;
        * duplicate event identifiers exist.

    Non-blocking conditions are logged as warnings (e.g. slurry events with no
    application method), so the user keeps full visibility without halting.

    Parameters
    ----------
    df : pandas.DataFrame
        Table returned by :func:`load_database`.

    Raises
    ------
    ValueError
        On any blocking structural problem.
    """
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required column(s): {missing}")

    if df["ID_evenement"].duplicated().any():
        dups = df.loc[df["ID_evenement"].duplicated(), "ID_evenement"].tolist()
        raise ValueError(f"Duplicate ID_evenement values found: {dups}")

    # Date must be coercible to datetime for the rotation split to be meaningful.
    parsed = pd.to_datetime(df["Date"], errors="coerce")
    n_bad_dates = int(parsed.isna().sum())
    if n_bad_dates:
        bad_ids = df.loc[parsed.isna(), "ID_evenement"].tolist()
        raise ValueError(
            f"{n_bad_dates} event(s) have an unparseable Date "
            f"(ID_evenement={bad_ids})."
        )

    # Non-blocking: slurry/manure events that lack an application method.
    organic_cats = {"Lisier", "Digestat liquide", "Fumier solide", "Autre organique"}
    no_method = df[
        df["Categorie"].isin(organic_cats) & df["Methode_application"].isna()
    ]
    if not no_method.empty:
        logger.warning(
            "%d organic event(s) have no Methode_application "
            "(EMEP cannot assign an emission factor for them): ID_evenement=%s",
            len(no_method), no_method["ID_evenement"].tolist(),
        )

    logger.info("Structural validation passed (%d events, no duplicates).", len(df))


# --------------------------------------------------------------------------- #
# Cleaning                                                                     #
# --------------------------------------------------------------------------- #

def clean_database(df: pd.DataFrame) -> pd.DataFrame:
    """Apply the two blocking corrections found during verification.

    1. Parse ``Date`` to a proper datetime dtype.
    2. Repair ``N_total_kgNha`` (French decimal comma -> dot) and cast to float,
       so the column is numeric. Legitimate empty cells stay as NaN.

    The function works on a copy and never fills missing values.

    Parameters
    ----------
    df : pandas.DataFrame
        Raw table.

    Returns
    -------
    pandas.DataFrame
        Cleaned copy with the same columns, in the same order.
    """
    out = df.copy()

    # (1) Normalise the date column.
    out["Date"] = pd.to_datetime(out["Date"], errors="coerce")

    # (2) Repair the text-typed N_total column without losing any event.
    if out["N_total_kgNha"].dtype == object:
        as_text = out["N_total_kgNha"].astype("string")
        repaired = as_text.str.replace(",", ".", regex=False)
        numeric = pd.to_numeric(repaired, errors="coerce")

        # A value that was non-empty but failed to parse is a real anomaly:
        # report it instead of silently turning it into NaN.
        newly_lost = out["N_total_kgNha"].notna() & numeric.isna()
        if newly_lost.any():
            bad = out.loc[newly_lost, ["ID_evenement", "N_total_kgNha"]]
            logger.warning(
                "Could not parse N_total_kgNha for %d row(s): %s",
                int(newly_lost.sum()),
                bad.to_dict("records"),
            )
        n_fixed = int((as_text.str.contains(",", na=False)).sum())
        if n_fixed:
            logger.info("Repaired %d N_total_kgNha cell(s) with comma decimals.", n_fixed)
        out["N_total_kgNha"] = numeric

    return out


# --------------------------------------------------------------------------- #
# Rotation split                                                              #
# --------------------------------------------------------------------------- #

def split_rotations(
    df: pd.DataFrame, cut_date: pd.Timestamp
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Partition events into first- and second-rotation subsets by Date.

    Parameters
    ----------
    df : pandas.DataFrame
        Cleaned table (Date already a datetime).
    cut_date : pandas.Timestamp
        Boundary. ``Date < cut_date`` -> first rotation;
        ``Date >= cut_date`` -> second rotation.

    Returns
    -------
    (first, second) : tuple of pandas.DataFrame
        The two subsets, each preserving the full column structure.
    """
    first = df[df["Date"] < cut_date].copy()
    second = df[df["Date"] >= cut_date].copy()

    # Integrity guard: the partition must be exhaustive and disjoint.
    if len(first) + len(second) != len(df):
        raise RuntimeError(
            "Rotation split is not exhaustive: "
            f"{len(first)} + {len(second)} != {len(df)}."
        )

    logger.info(
        "Split at %s -> first rotation: %d events | second rotation: %d events.",
        cut_date.date(), len(first), len(second),
    )
    return first, second


def relabel_second_rotation(df: pd.DataFrame) -> pd.DataFrame:
    """Relabel replaced systems in the second-rotation subset.

    CTR -> COM and MF -> LOM, per the platform change documented in the
    Trajectoire brochure. Operates on a copy.

    Parameters
    ----------
    df : pandas.DataFrame
        Second-rotation subset.

    Returns
    -------
    pandas.DataFrame
        Subset with the ``Systeme`` codes updated.
    """
    out = df.copy()
    counts = out["Systeme"].isin(SECOND_ROTATION_RELABEL).sum()
    out["Systeme"] = out["Systeme"].replace(SECOND_ROTATION_RELABEL)
    if counts:
        logger.info(
            "Relabelled %d second-rotation event(s): %s.",
            int(counts),
            ", ".join(f"{k}->{v}" for k, v in SECOND_ROTATION_RELABEL.items()),
        )
    return out


# --------------------------------------------------------------------------- #
# Export                                                                       #
# --------------------------------------------------------------------------- #

def export_subsets(
    first: pd.DataFrame, second: pd.DataFrame, output_dir: Path
) -> tuple[Path, Path]:
    """Write both subsets to Excel, preserving columns and empty cells.

    Parameters
    ----------
    first, second : pandas.DataFrame
        The two rotation subsets.
    output_dir : Path
        Destination directory (created if needed).

    Returns
    -------
    (first_path, second_path) : tuple of Path
        Paths to the written files.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    first_path = output_dir / "DB_first_rotation.xlsx"
    second_path = output_dir / "DB_second_rotation.xlsx"

    # index=False keeps the exported sheet identical in shape to the source.
    first.to_excel(first_path, sheet_name="Donnees_plates", index=False)
    second.to_excel(second_path, sheet_name="Donnees_plates", index=False)

    logger.info("Wrote '%s' (%d events).", first_path.name, len(first))
    logger.info("Wrote '%s' (%d events).", second_path.name, len(second))
    return first_path, second_path


# --------------------------------------------------------------------------- #
# Orchestration & CLI                                                         #
# --------------------------------------------------------------------------- #

def run(input_path: Path, output_dir: Path, cut_date: pd.Timestamp) -> None:
    """Full pipeline: load -> validate -> clean -> split -> relabel -> export."""
    df = load_database(input_path)
    validate_database(df)
    df = clean_database(df)
    first, second = split_rotations(df, cut_date)
    second = relabel_second_rotation(second)
    export_subsets(first, second, output_dir)
    logger.info("Done.")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Define and parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Split the Trajectoire fertilization database into "
                    "first- and second-rotation subsets for EMEP Tier 2.",
    )
    # Default paths point to the local Windows workstation. Override on any
    # other machine with --input / --output-dir.
    default_input = Path(r"C:\Users\dzuni\OneDrive\Documentos\INTERNSHIP\DB_plain_clean.xlsx")
    default_output = Path(r"C:\Users\dzuni\OneDrive\Documentos\INTERNSHIP\Resultats_FINALES")
    parser.add_argument(
        "--input", type=Path, default=default_input,
        help=f"Path to the source workbook (default: {default_input}).",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=default_output,
        help=f"Directory for the two output files (default: {default_output}).",
    )
    parser.add_argument(
        "--cut-date", type=str, default=DEFAULT_CUT_DATE,
        help=f"Second-rotation start date, YYYY-MM-DD (default: {DEFAULT_CUT_DATE}).",
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Enable debug-level logging.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns 0 on success, 1 on a handled error."""
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)-8s %(message)s",
    )

    # Validate the cut-off date early with a clear message.
    try:
        cut_date = pd.Timestamp(args.cut_date)
    except ValueError:
        logger.error("Invalid --cut-date '%s'; expected format YYYY-MM-DD.", args.cut_date)
        return 1

    try:
        run(args.input, args.output_dir, cut_date)
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        logger.error("%s", exc)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
