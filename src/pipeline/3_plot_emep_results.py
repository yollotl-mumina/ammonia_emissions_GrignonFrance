#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
plot_emep_results.py
====================

Generate the standard NH3 figure set from the EMEP Tier 2 results produced by
``run_emep_tier2.py``. For every workbook it reads ``<file>_EMEP/events_emep.csv``
and writes the figures to ``<file>_EMEP/figures/``.

Figures (per file)
------------------
    F1  Absolute NH3-N emissions by cropping system        (kg NH3-N/ha)
    F2  Emission intensity by system                       (% of applied N)
    F3  NH3-N emissions by product category                (kg NH3-N/ha)
    F4  Effect of the Entec correction: baseline vs corrected, by system
    F5  NH3-N emissions by system, stacked by product category

All figure text is in English. Input CSVs are never modified.

>>> Run run_emep_tier2.py first to create the *_EMEP folders. <<<

Author: Daniela Zuniga-Jimenez - AgroParisTech / UMR ECOSYS - 2026
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")              # file output only; no interactive backend
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# ─────────────────────────────────────────────────────────────────────────────
#  CONFIGURATION — edit only this block
# ─────────────────────────────────────────────────────────────────────────────

#: Workbooks whose *_EMEP result folders should be plotted.
DEFAULT_INPUTS: tuple[Path, ...] = (
    Path(r"C:\Users\dzuni\OneDrive\Documentos\INTERNSHIP\DB_plain_clean.xlsx"),
    Path(r"C:\Users\dzuni\OneDrive\Documentos\INTERNSHIP\Resultats_FINALES\DB_first_rotation.xlsx"),
    Path(r"C:\Users\dzuni\OneDrive\Documentos\INTERNSHIP\Resultats_FINALES\DB_second_rotation.xlsx"),
)

FIG_EXT: str = "png"               # "png" or "pdf"

# Per-file subtitles (matched by file stem; a sensible default is used otherwise).
SUBTITLES: dict[str, str] = {
    "DB_plain_clean":     "EMEP/EEA Guidebook 2023, Tier 2 — full inventory (2018–2025)",
    "DB_first_rotation":  "EMEP/EEA Guidebook 2023, Tier 2 — first rotation",
    "DB_second_rotation": "EMEP/EEA Guidebook 2023, Tier 2 — second rotation (COM/LOM)",
}

# Plot style.
plt.rcParams.update({"font.size": 11, "axes.titlesize": 13,
                     "axes.titleweight": "bold", "figure.dpi": 150,
                     "axes.spines.top": False, "axes.spines.right": False})
BLUE, ORANGE, GREY = "#2F5597", "#C55A11", "#9AA0A6"

# French category labels -> English display names.
CAT_EN: dict[str, str] = {
    "Solution azotée (UAN)": "UAN solution", "Entec": "Entec (ASN)",
    "Urée": "Urea", "Thiosulfate": "Thiosulphate",
    "Ammonitrate": "Ammonium nitrate", "Lisier": "Cattle slurry",
    "Digestat liquide": "Liquid digestate", "Fumier solide": "Solid manure",
    "Autre organique": "Other organic",
    "Oligo/biostimulant": "Micronutrient/biostimulant", "Additif": "Additive",
}
# Stable colour per (English) category, for the stacked figure F5.
CAT_COLORS: dict[str, str] = {
    "UAN solution": "#2F5597", "Entec (ASN)": "#C55A11", "Urea": "#7030A0",
    "Ammonium nitrate": "#548235", "Thiosulphate": "#BF9000",
    "Cattle slurry": "#1F9E89", "Liquid digestate": "#4FB0AE",
    "Solid manure": "#8C6D4F", "Other organic": "#C0504D",
    "Micronutrient/biostimulant": "#9AA0A6", "Additive": "#BFBFBF",
}
#: Preferred left-to-right system order (unknown systems are appended).
SYSTEM_ORDER: tuple[str, ...] = ("SCA", "GHG", "HYP", "CTR", "COM",
                                 "LI", "OF", "MF", "LOM")

logger = logging.getLogger("plot_emep")


# ─────────────────────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _ordered_systems(systems: list[str]) -> list[str]:
    """Return ``systems`` in the preferred order, appending any extras."""
    known = [s for s in SYSTEM_ORDER if s in systems]
    extra = sorted(s for s in systems if s not in SYSTEM_ORDER)
    return known + extra


def _subtitle_for(stem: str) -> str:
    """Subtitle for a file stem, with a generic fallback."""
    return SUBTITLES.get(stem, "EMEP/EEA Guidebook 2023, Tier 2")


def _titles(ax: plt.Axes, title: str, subtitle: str) -> None:
    """Set a bold title with a grey subtitle underneath, without overlap."""
    ax.set_title(title, pad=26)
    ax.text(0.0, 1.015, subtitle, transform=ax.transAxes,
            fontsize=9, color=GREY, va="bottom")


def _save(fig: plt.Figure, fig_dir: Path, name: str) -> None:
    """Save and close a figure, creating the directory if needed."""
    fig_dir.mkdir(parents=True, exist_ok=True)
    path = fig_dir / f"{name}.{FIG_EXT}"
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    logger.info("    wrote %s", path.name)


def load_events(emep_dir: Path) -> pd.DataFrame:
    """Load ``events_emep.csv`` from a result folder.

    Raises
    ------
    FileNotFoundError
        If the expected CSV is absent (run_emep_tier2.py was not run).
    """
    csv = emep_dir / "events_emep.csv"
    if not csv.is_file():
        raise FileNotFoundError(
            f"{csv} not found. Run run_emep_tier2.py first to create it."
        )
    return pd.read_csv(csv)


# ─────────────────────────────────────────────────────────────────────────────
#  FIGURES
# ─────────────────────────────────────────────────────────────────────────────

def fig_by_system(df: pd.DataFrame, subtitle: str) -> plt.Figure:
    """F1 — absolute NH3-N emissions by cropping system."""
    s = df.groupby("Systeme")["NH3_emis_kgNha_EMEP"].sum()
    order = _ordered_systems(list(s.index))
    s = s.reindex(order)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.bar(s.index, s.values, color=BLUE)
    for x, v in zip(s.index, s.values):
        ax.text(x, v, f"{v:.0f}", ha="center", va="bottom", fontsize=9)
    ax.set_ylabel("NH$_3$-N emissions (kg N/ha)")
    _titles(ax, "Absolute NH$_3$-N emissions by cropping system", subtitle)
    return fig


def fig_intensity(df: pd.DataFrame, subtitle: str) -> plt.Figure:
    """F2 — emission intensity (% of applied N) by system."""
    g = df.groupby("Systeme").agg(
        emis=("NH3_emis_kgNha_EMEP", "sum"),
        napp=("N_applied_kgNha", "sum"),
    )
    g["pct"] = np.where(g["napp"] > 0, 100 * g["emis"] / g["napp"], np.nan)
    order = _ordered_systems(list(g.index))
    g = g.reindex(order)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.bar(g.index, g["pct"].values, color=ORANGE)
    for x, v in zip(g.index, g["pct"].values):
        if not np.isnan(v):
            ax.text(x, v, f"{v:.1f}%", ha="center", va="bottom", fontsize=9)
    ax.set_ylabel("Intensity (% of applied N volatilized)")
    _titles(ax, "NH$_3$-N emission intensity by cropping system", subtitle)
    return fig


def fig_by_category(df: pd.DataFrame, subtitle: str) -> plt.Figure:
    """F3 — NH3-N emissions by product category (English labels)."""
    s = df.groupby("Categorie")["NH3_emis_kgNha_EMEP"].sum().sort_values()
    s = s[s > 0]  # drop non-emitting categories from this view
    labels = [CAT_EN.get(c, c) for c in s.index]
    colors = [CAT_COLORS.get(lbl, BLUE) for lbl in labels]

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.barh(labels, s.values, color=colors)
    for y, v in enumerate(s.values):
        ax.text(v, y, f" {v:.0f}", va="center", fontsize=9)
    ax.set_xlabel("NH$_3$-N emissions (kg N/ha)")
    _titles(ax, "NH$_3$-N emissions by product category", subtitle)
    return fig


def fig_baseline_vs_corrected(df: pd.DataFrame, subtitle: str) -> plt.Figure:
    """F4 — baseline vs corrected NH3-N by system (Entec ASN effect)."""
    g = df.groupby("Systeme").agg(
        baseline=("NH3_emis_kgNha_base", "sum"),
        corrected=("NH3_emis_kgNha_EMEP", "sum"),
    )
    order = _ordered_systems(list(g.index))
    g = g.reindex(order)
    x = np.arange(len(g))
    w = 0.4

    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.bar(x - w / 2, g["baseline"], width=w, label="Baseline (Entec as AS)", color=GREY)
    ax.bar(x + w / 2, g["corrected"], width=w, label="Corrected (Entec as ASN)", color=BLUE)
    ax.set_xticks(x)
    ax.set_xticklabels(g.index)
    ax.set_ylabel("NH$_3$-N emissions (kg N/ha)")
    _titles(ax, "Effect of the Entec correction, by cropping system", subtitle)
    ax.legend(frameon=False, fontsize=9)
    return fig


def fig_stacked(df: pd.DataFrame, subtitle: str) -> plt.Figure:
    """F5 — NH3-N by system, stacked by product category."""
    df = df.copy()
    df["Cat_EN"] = df["Categorie"].map(lambda c: CAT_EN.get(c, c))
    pivot = (df.pivot_table(index="Systeme", columns="Cat_EN",
                            values="NH3_emis_kgNha_EMEP", aggfunc="sum",
                            fill_value=0.0))
    order = _ordered_systems(list(pivot.index))
    pivot = pivot.reindex(order)
    # Keep only categories that actually emit something, ordered by total.
    totals = pivot.sum().sort_values(ascending=False)
    cats = [c for c in totals.index if totals[c] > 0]

    fig, ax = plt.subplots(figsize=(9, 5))
    bottom = np.zeros(len(pivot))
    for cat in cats:
        vals = pivot[cat].values
        ax.bar(pivot.index, vals, bottom=bottom,
               color=CAT_COLORS.get(cat, BLUE), label=cat)
        bottom += vals
    ax.set_ylabel("NH$_3$-N emissions (kg N/ha)")
    _titles(ax, "NH$_3$-N emissions by system, stacked by product category", subtitle)
    ax.legend(frameon=False, fontsize=8, ncol=2, loc="upper right")
    return fig


# ─────────────────────────────────────────────────────────────────────────────
#  PER-FILE DRIVER
# ─────────────────────────────────────────────────────────────────────────────

#: (function, output filename) for the figure set.
FIGURES = (
    (fig_by_system,             "F1_emissions_by_system"),
    (fig_intensity,             "F2_intensity_by_system"),
    (fig_by_category,           "F3_emissions_by_category"),
    (fig_baseline_vs_corrected, "F4_baseline_vs_corrected"),
    (fig_stacked,               "F5_stacked_by_category"),
)


def plot_file(input_path: Path) -> None:
    """Produce the full figure set for one workbook's EMEP results."""
    emep_dir = input_path.with_name(input_path.stem + "_EMEP")
    logger.info("Plotting %s", emep_dir.name)
    df = load_events(emep_dir)

    subtitle = _subtitle_for(input_path.stem)
    fig_dir = emep_dir / "figures"
    for func, name in FIGURES:
        try:
            fig = func(df, subtitle)
            _save(fig, fig_dir, name)
        except Exception as exc:  # noqa: BLE001 - one bad figure must not stop the rest
            logger.error("    %s failed: %s", name, exc)


# ─────────────────────────────────────────────────────────────────────────────
#  CLI
# ─────────────────────────────────────────────────────────────────────────────

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot the EMEP Tier 2 NH3 results for the Trajectoire workbooks.",
    )
    parser.add_argument(
        "--inputs", type=Path, nargs="+", default=list(DEFAULT_INPUTS),
        help="Workbooks whose *_EMEP folders should be plotted "
             "(default: the three Trajectoire files).",
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
            plot_file(Path(path))
        except FileNotFoundError as exc:
            logger.error("%s", exc)
            failures += 1

    if failures:
        logger.error("Finished with %d file(s) failed.", failures)
        return 1
    logger.info("All figures generated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
