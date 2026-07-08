#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
split_alfam2_rotations.py
=========================

Split the ALFAM2 hourly input table (``ALFAM2_entrada_horaria.xlsx``) into two
subsets — first and second rotation — using exactly the same cut-off applied to
``DB_plain_clean.xlsx`` (sowing date of the second rotation, 2022-08-01).

The file is in ALFAM2 long format: one row per (event x hour), grouped by
``ID_evenement`` with time index ``ct`` (hours since application). Because the
application ``Date`` is constant within an event, splitting by ``Date`` keeps
each event's full hourly series on a single side of the boundary — no event is
ever cut in half.

Consistency with the DB processing
----------------------------------
* Same cut-off date (configurable, default 2022-08-01).
* In the SECOND-rotation subset only, the replaced systems are relabelled to
  match ``DB_second_rotation.xlsx``: CTR -> COM, MF -> LOM. This keeps the
  join keys aligned between the EMEP and ALFAM2 second-rotation datasets.
  Set RELABEL_SECOND_ROTATION = False to keep the raw CTR/MF labels.

The ALFAM2 model applies only to liquid organic effluents; this file already
contains only Lisier and liquid digestate events (man.source = cattle).

Usage
-----
    python split_alfam2_rotations.py
    python split_alfam2_rotations.py --input path/to/ALFAM2_entrada_horaria.xlsx \
                                     --output-dir path/to/out --cut-date 2022-08-01

Author: Daniela Zuniga-Jimenez - AgroParisTech / UMR ECOSYS - 2026
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

# ─────────────────────────────────────────────────────────────────────────────
#  CONFIGURATION — edit only this block
# ─────────────────────────────────────────────────────────────────────────────

#: Sheet holding the hourly series. None = auto-detect the sheet with the data.
SHEET_NAME: str | None = "ALFAM2_horario"

#: Boundary between rotations (sowing date of rotation 2), same as the DB split.
DEFAULT_CUT_DATE: str = "2022-08-01"

#: Relabel replaced systems in the SECOND-rotation subset, to match the DB.
RELABEL_SECOND_ROTATION: bool = True
SECOND_ROTATION_RELABEL: dict[str, str] = {
    "CTR": "COM",  # Control -> Crop-Oriented Methanization
    "MF": "LOM",   # Mixed Farming -> Livestock-Oriented Methanization
}

#: Columns required by ALFAM2 (validated before the split).
REQUIRED_COLUMNS: tuple[str, ...] = (
    "ID_evenement", "Systeme", "Categorie", "Date", "ct",
    "TAN.app", "app.rate", "app.mthd", "man.dm", "man.ph", "man.source",
    "air.temp", "wind.2m", "rain.rate", "rain.cum", "incorp", "t.incorp",
)

#: Grouping and time keys of the ALFAM2 long format.
EVENT_KEY: str = "ID_evenement"
TIME_KEY: str = "ct"
DATE_KEY: str = "Date"

logger = logging.getLogger("split_alfam2")


# ─────────────────────────────────────────────────────────────────────────────
#  Loading & validation
# ─────────────────────────────────────────────────────────────────────────────

def _detect_sheet(path: Path) -> str:
    """Return the configured sheet, or the sheet with the most rows."""
    xls = pd.ExcelFile(path)
    if SHEET_NAME is not None and SHEET_NAME in xls.sheet_names:
        return SHEET_NAME
    best, best_rows = xls.sheet_names[0], -1
    for name in xls.sheet_names:
        rows = len(pd.read_excel(path, sheet_name=name, header=None))
        if rows > best_rows:
            best, best_rows = name, rows
    return best


def load_alfam2(path: Path) -> pd.DataFrame:
    """Read the ALFAM2 hourly table from the workbook.

    Raises
    ------
    FileNotFoundError
        If the workbook does not exist.
    ValueError
        If the sheet cannot be read or is empty.
    """
    if not path.is_file():
        raise FileNotFoundError(f"Input workbook not found: {path}")

    try:
        sheet = _detect_sheet(path)
    except Exception as exc:  # noqa: BLE001 - surface reader failures clearly
        raise ValueError(f"Could not open '{path}' as an Excel workbook: {exc}") from exc

    df = pd.read_excel(path, sheet_name=sheet, header=0)
    df = df.dropna(how="all")
    if df.empty:
        raise ValueError(f"Sheet '{sheet}' contains no data rows.")

    logger.info("Loaded %d rows x %d columns from '%s' (sheet '%s').",
                df.shape[0], df.shape[1], path.name, sheet)
    return df


def validate_alfam2(df: pd.DataFrame) -> None:
    """Check ALFAM2 structural requirements; raise on blocking problems.

    Blocking (raise ``ValueError``):
        * a required column is missing;
        * the ``Date`` column cannot be parsed to datetime;
        * an event spans more than one application date (would split a series).

    Non-blocking conditions are logged as warnings.

    Raises
    ------
    ValueError
        On any blocking structural problem.
    """
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing ALFAM2 column(s): {missing}")

    parsed = pd.to_datetime(df[DATE_KEY], errors="coerce")
    if parsed.isna().any():
        bad = df.loc[parsed.isna(), EVENT_KEY].unique().tolist()
        raise ValueError(f"Unparseable Date for event(s): {bad}")

    # Each event must carry a single application date, otherwise a date-based
    # split could break its hourly series across the two subsets.
    dates_per_event = df.assign(_d=parsed).groupby(EVENT_KEY)["_d"].nunique()
    multi = dates_per_event[dates_per_event > 1].index.tolist()
    if multi:
        raise ValueError(
            f"Event(s) {multi} have more than one application Date; "
            "a date-based split would break their hourly series."
        )

    # Non-blocking: t.incorp should be set exactly where incorp != 'none'.
    incorporated = df["incorp"].astype(str).str.lower() != "none"
    missing_tincorp = incorporated & df["t.incorp"].isna()
    if missing_tincorp.any():
        ev = df.loc[missing_tincorp, EVENT_KEY].unique().tolist()
        logger.warning("Event(s) %s are incorporated but miss t.incorp.", ev)

    n_events = df[EVENT_KEY].nunique()
    logger.info("Validation passed: %d events, %d hourly rows.", n_events, len(df))


# ─────────────────────────────────────────────────────────────────────────────
#  Split & relabel
# ─────────────────────────────────────────────────────────────────────────────

def split_rotations(
    df: pd.DataFrame, cut_date: pd.Timestamp
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Partition the hourly table into first/second rotation by application date.

    ``Date < cut_date`` -> first rotation; ``Date >= cut_date`` -> second.
    The whole hourly series of an event stays together (Date is event-constant).

    Returns
    -------
    (first, second) : tuple of pandas.DataFrame
    """
    dates = pd.to_datetime(df[DATE_KEY])
    first = df[dates < cut_date].copy()
    second = df[dates >= cut_date].copy()

    if len(first) + len(second) != len(df):
        raise RuntimeError(
            f"Split not exhaustive: {len(first)} + {len(second)} != {len(df)}."
        )

    logger.info(
        "Split at %s -> R1: %d rows / %d events | R2: %d rows / %d events.",
        cut_date.date(),
        len(first), first[EVENT_KEY].nunique(),
        len(second), second[EVENT_KEY].nunique(),
    )
    return first, second


def relabel_second_rotation(df: pd.DataFrame) -> pd.DataFrame:
    """Relabel CTR->COM and MF->LOM in the second-rotation subset (a copy)."""
    out = df.copy()
    affected = int(out["Systeme"].isin(SECOND_ROTATION_RELABEL).sum())
    out["Systeme"] = out["Systeme"].replace(SECOND_ROTATION_RELABEL)
    if affected:
        logger.info("Relabelled %d second-rotation rows: %s.", affected,
                    ", ".join(f"{k}->{v}" for k, v in SECOND_ROTATION_RELABEL.items()))
    return out


# ─────────────────────────────────────────────────────────────────────────────
#  Export
# ─────────────────────────────────────────────────────────────────────────────

def export_subsets(
    first: pd.DataFrame, second: pd.DataFrame, output_dir: Path
) -> tuple[Path, Path]:
    """Write both subsets to Excel, preserving the ALFAM2 long-format structure."""
    output_dir.mkdir(parents=True, exist_ok=True)
    first_path = output_dir / "ALFAM2_first_rotation.xlsx"
    second_path = output_dir / "ALFAM2_second_rotation.xlsx"

    # Keep the same sheet name and column order; do not write the index.
    first.to_excel(first_path, sheet_name="ALFAM2_horario", index=False)
    second.to_excel(second_path, sheet_name="ALFAM2_horario", index=False)

    logger.info("Wrote '%s' (%d rows).", first_path.name, len(first))
    logger.info("Wrote '%s' (%d rows).", second_path.name, len(second))
    return first_path, second_path


# ─────────────────────────────────────────────────────────────────────────────
#  Orchestration & CLI
# ─────────────────────────────────────────────────────────────────────────────

def run(input_path: Path, output_dir: Path, cut_date: pd.Timestamp) -> None:
    """Full pipeline: load -> validate -> split -> relabel -> export."""
    df = load_alfam2(input_path)
    validate_alfam2(df)
    first, second = split_rotations(df, cut_date)
    if RELABEL_SECOND_ROTATION:
        second = relabel_second_rotation(second)
    export_subsets(first, second, output_dir)
    logger.info("Done.")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Define and parse command-line arguments."""
    default_input = Path(r"C:\Users\dzuni\OneDrive\Documentos\INTERNSHIP\ALFAM2_entrada_horaria.xlsx")
    default_output = Path(r"C:\Users\dzuni\OneDrive\Documentos\INTERNSHIP\Resultats_FINALES")

    parser = argparse.ArgumentParser(
        description="Split the ALFAM2 hourly input into first/second rotation, "
                    "consistently with the DB_plain_clean split.",
    )
    parser.add_argument(
        "--input", type=Path, default=default_input,
        help=f"Path to ALFAM2_entrada_horaria.xlsx (default: {default_input}).",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=default_output,
        help=f"Directory for the two output files (default: {default_output}).",
    )
    parser.add_argument(
        "--cut-date", type=str, default=DEFAULT_CUT_DATE,
        help=f"Second-rotation start date, YYYY-MM-DD (default: {DEFAULT_CUT_DATE}).",
    )
    parser.add_argument("--verbose", action="store_true",
                        help="Enable debug-level logging.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns 0 on success, 1 on a handled error."""
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)-8s %(message)s",
    )

    try:
        cut_date = pd.Timestamp(args.cut_date)
    except ValueError:
        logger.error("Invalid --cut-date '%s'; expected YYYY-MM-DD.", args.cut_date)
        return 1

    try:
        run(args.input, args.output_dir, cut_date)
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        logger.error("%s", exc)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
