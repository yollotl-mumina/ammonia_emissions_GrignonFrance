#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
compare_alfam2_emep.py
======================

Compare the two NH3 models — ALFAM2 vs EMEP Tier 2 — per event, for three
pairings of result files:

    original         : ALFAM2_entrada_horaria   vs  DB_plain_clean
    first_rotation   : ALFAM2_first_rotation     vs  DB_first_rotation
    second_rotation  : ALFAM2_second_rotation    vs  DB_second_rotation

ALFAM2 only models liquid organic effluents (Lisier, liquid digestate), so the
comparison is made on the events both models share, joined by ID_evenement.
EMEP computes those events as TAN x EF_organic (a fixed fraction), whereas
ALFAM2 resolves them dynamically — the key contrast is the sensitivity to the
application method (bsth = trailing hose vs bc = broadcast) that EMEP's fixed
factor cannot capture.

For each pairing the script writes, to RESULTS_DIR/comparison_<tag>/ :
    comparison_<tag>.csv          per-event table (EMEP, ALFAM2, diff, ratio)
    C1_dumbbell.<ext>             per-event EMEP vs ALFAM2 (connected dots)
    C2_scatter.<ext>              EMEP vs ALFAM2 with the 1:1 line
    C3_difference.<ext>           (ALFAM2 - EMEP) per event, by method
    C4_pctTAN_by_method.<ext>     % of TAN by method: EMEP (fixed) vs ALFAM2

Input CSVs are produced by run_emep_tier2.py and run_alfam2.R and are never
modified.

Author: Daniela Zuniga-Jimenez - AgroParisTech / UMR ECOSYS - 2026
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# ─────────────────────────────────────────────────────────────────────────────
#  CONFIGURATION — edit only this block
# ─────────────────────────────────────────────────────────────────────────────

#: Base folders. The EMEP folder of the full inventory sits next to the source
#: workbook (INTERNSHIP_DIR); the rotation EMEP folders and all ALFAM2 outputs
#: sit in RESULTS_DIR. Override both on the command line if your layout differs.
INTERNSHIP_DIR: Path = Path(r"C:\Users\dzuni\OneDrive\Documentos\INTERNSHIP")
RESULTS_DIR: Path = INTERNSHIP_DIR / "Resultats_FINALES"

FIG_EXT: str = "png"

# Plot style (same palette as the EMEP/ALFAM2 figures).
plt.rcParams.update({"font.size": 11, "axes.titlesize": 13,
                     "axes.titleweight": "bold", "figure.dpi": 150,
                     "axes.spines.top": False, "axes.spines.right": False})
BLUE, ORANGE, GREY = "#2F5597", "#C55A11", "#9AA0A6"
EMEP_COLOR, ALFAM2_COLOR = GREY, BLUE

METHOD_EN: dict[str, str] = {"bsth": "Trailing hose (bsth)", "bc": "Broadcast (bc)"}
METHOD_COLORS: dict[str, str] = {"bsth": BLUE, "bc": ORANGE}

logger = logging.getLogger("compare_models")

# Custom per-event display names (by ID_evenement). Events not listed fall back
# to "id . method". Keep in sync with the plotting scripts.
EVENT_LABELS: dict[int, str] = {
    96:  "COM-2025 (Digestat liquide 5u)",
    97:  "COM-2025 (Digestat liquide 4u)",
    130: "MF-2018 (Lisier 2u)",
    133: "MF-2019 (Lisier 3u)",
    136: "MF-2021 (Lisier 4u)",
    140: "MF-2022 (Lisier 3u)",
    141: "MF-2022 (Lisier 3u)",
    143: "LOM-2022 (Lisier 3u)",
    148: "LOM-2024 (Lisier 2u)",
    150: "LOM-2025 (Digestat liquide 5u)",
    151: "LOM-2025 (Digestat liquide 4u)",
}


def build_pairings(internship: Path, results: Path
                   ) -> tuple[tuple[str, list[Path], Path, str], ...]:
    """Return (tag, emep_csv_candidates, alfam2_by_event_csv, subtitle) tuples.

    EMEP is a per-event model: an event's emission is identical whether it is
    computed on the full inventory or on a rotation subset (it depends only on
    that event's N/TAN/category/EF, and the COM/LOM relabelling does not change
    the value). So the full-inventory EMEP file is always a valid source. Each
    pairing therefore lists the rotation-specific EMEP file first and the full
    EMEP file as a fallback; the rotation membership comes from the ALFAM2 side,
    which is already split. The first existing candidate is used.
    """
    full_emep = internship / "DB_plain_clean_EMEP" / "events_emep.csv"
    return (
        ("original",
         [full_emep],
         results / "ALFAM2_entrada_horaria_alfam2_by_event.csv",
         "ALFAM2 vs EMEP Tier 2 — full set (2018–2025)"),
        ("first_rotation",
         [results / "DB_first_rotation_EMEP" / "events_emep.csv", full_emep],
         results / "ALFAM2_first_rotation_alfam2_by_event.csv",
         "ALFAM2 vs EMEP Tier 2 — first rotation"),
        ("second_rotation",
         [results / "DB_second_rotation_EMEP" / "events_emep.csv", full_emep],
         results / "ALFAM2_second_rotation_alfam2_by_event.csv",
         "ALFAM2 vs EMEP Tier 2 — second rotation (COM/LOM)"),
    )


# ─────────────────────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _first_col(df: pd.DataFrame, candidates: list[str], what: str) -> str:
    """Return the first present column among ``candidates`` or raise."""
    for c in candidates:
        if c in df.columns:
            return c
    raise KeyError(f"Could not find the {what} column "
                   f"(tried {candidates}); available: {list(df.columns)}")


def _method_label(code: str) -> str:
    return METHOD_EN.get(str(code), str(code))


def _method_color(code: str) -> str:
    return METHOD_COLORS.get(str(code), GREY)


def _titles(ax: plt.Axes, title: str, subtitle: str) -> None:
    ax.set_title(title, pad=26)
    ax.text(0.0, 1.015, subtitle, transform=ax.transAxes,
            fontsize=9, color=GREY, va="bottom")


def _save(fig: plt.Figure, fig_dir: Path, name: str) -> None:
    fig_dir.mkdir(parents=True, exist_ok=True)
    path = fig_dir / f"{name}.{FIG_EXT}"
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    logger.info("    wrote %s", path.name)


# ─────────────────────────────────────────────────────────────────────────────
#  BUILD THE PER-EVENT COMPARISON TABLE
# ─────────────────────────────────────────────────────────────────────────────

def build_comparison(emep_candidates: list[Path], alfam2_csv: Path) -> pd.DataFrame:
    """Join EMEP and ALFAM2 per-event results on ID_evenement.

    ``emep_candidates`` is tried in order; the first existing file is used as
    the EMEP source (rotation-specific if present, else the full inventory).
    The join is inner, so the rotation membership is set by the ALFAM2 file.

    Returns a tidy table with both models' NH3-N, their difference, ratio, and
    each model's emission as % of applied TAN.

    Raises
    ------
    FileNotFoundError
        If the ALFAM2 file or every EMEP candidate is missing.
    ValueError
        If the join yields no common events.
    """
    emep_csv = next((p for p in emep_candidates if p.is_file()), None)
    if emep_csv is None:
        raise FileNotFoundError(
            "No EMEP events file found. Tried:\n  "
            + "\n  ".join(str(p) for p in emep_candidates)
            + "\nRun run_emep_tier2.py (it creates DB_plain_clean_EMEP/events_emep.csv)."
        )
    if not alfam2_csv.is_file():
        raise FileNotFoundError(
            f"{alfam2_csv} not found. Run run_alfam2.R to create it."
        )
    logger.info("  EMEP source: %s", emep_csv.name
                if emep_csv.parent.name == "DB_plain_clean_EMEP"
                else f"{emep_csv.parent.name}/{emep_csv.name}")

    emep = pd.read_csv(emep_csv)
    alf = pd.read_csv(alfam2_csv)

    emep_emis = _first_col(emep, ["NH3_emis_kgNha_EMEP", "NH3_emis_kgNha"],
                           "EMEP emission")
    alf_emis = _first_col(alf, ["NH3N_kgNha"], "ALFAM2 emission")
    alf_mthd = _first_col(alf, ["app_mthd", "app.mthd"], "application method")
    alf_tan = _first_col(alf, ["TAN_app_kgNha", "TAN.app"], "applied TAN")

    # Slim each side to the needed columns, then inner-join on the event id.
    left = alf[["ID_evenement", "Systeme", "Categorie", "Date",
                alf_mthd, alf_tan, alf_emis]].copy()
    left = left.rename(columns={alf_mthd: "app_mthd", alf_tan: "TAN_kgNha",
                                alf_emis: "ALFAM2_kgNha"})
    right = emep[["ID_evenement", emep_emis]].copy()
    right = right.rename(columns={emep_emis: "EMEP_kgNha"})

    merged = left.merge(right, on="ID_evenement", how="inner")
    if merged.empty:
        raise ValueError("No common events between EMEP and ALFAM2 outputs "
                         "(check that both cover the same ID_evenement).")

    # Comparison metrics. Guard divisions against zero.
    merged["diff_kgNha"] = merged["ALFAM2_kgNha"] - merged["EMEP_kgNha"]
    merged["ratio_A_over_E"] = np.where(
        merged["EMEP_kgNha"] > 0,
        merged["ALFAM2_kgNha"] / merged["EMEP_kgNha"], np.nan)
    merged["EMEP_pctTAN"] = np.where(
        merged["TAN_kgNha"] > 0,
        100 * merged["EMEP_kgNha"] / merged["TAN_kgNha"], np.nan)
    merged["ALFAM2_pctTAN"] = np.where(
        merged["TAN_kgNha"] > 0,
        100 * merged["ALFAM2_kgNha"] / merged["TAN_kgNha"], np.nan)

    merged = merged.sort_values(["Date", "ID_evenement"]).reset_index(drop=True)
    return merged


# ─────────────────────────────────────────────────────────────────────────────
#  FIGURES
# ─────────────────────────────────────────────────────────────────────────────

def _event_labels(df: pd.DataFrame) -> list[str]:
    """Per-event labels: custom name if defined, else 'id . method'."""
    return [EVENT_LABELS.get(int(i), f"{int(i)} \u00b7 {m}")
            for i, m in zip(df["ID_evenement"], df["app_mthd"])]


def fig_dumbbell(df: pd.DataFrame, subtitle: str) -> plt.Figure:
    """C1 — per-event EMEP vs ALFAM2 connected by a line (dumbbell)."""
    d = df.sort_values("EMEP_kgNha").reset_index(drop=True)
    y = np.arange(len(d))
    labels = _event_labels(d)

    fig, ax = plt.subplots(figsize=(8.5, max(4, 0.5 * len(d) + 1.5)))
    ax.hlines(y, d["EMEP_kgNha"], d["ALFAM2_kgNha"], color="#CCCCCC", lw=2, zorder=1)
    ax.scatter(d["EMEP_kgNha"], y, color=EMEP_COLOR, s=55, zorder=2, label="EMEP Tier 2")
    ax.scatter(d["ALFAM2_kgNha"], y, color=ALFAM2_COLOR, s=55, zorder=2, label="ALFAM2")
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.set_xlabel("NH$_3$-N emission (kg N/ha)")
    ax.set_ylabel("Event")
    _titles(ax, "EMEP vs ALFAM2 per event", subtitle)
    ax.legend(frameon=False, fontsize=9, loc="lower right")
    return fig


def fig_scatter(df: pd.DataFrame, subtitle: str) -> plt.Figure:
    """C2 — EMEP (x) vs ALFAM2 (y) scatter with the 1:1 line, by method."""
    fig, ax = plt.subplots(figsize=(6.5, 6.5))
    lim = float(np.nanmax([df["EMEP_kgNha"].max(), df["ALFAM2_kgNha"].max()])) * 1.1
    lim = max(lim, 1.0)
    ax.plot([0, lim], [0, lim], color=GREY, ls="--", lw=1, label="1:1 line")
    for m, sub in df.groupby("app_mthd"):
        ax.scatter(sub["EMEP_kgNha"], sub["ALFAM2_kgNha"],
                   color=_method_color(m), s=55, edgecolor="white",
                   label=_method_label(m), zorder=3)
    ax.set_xlim(0, lim)
    ax.set_ylim(0, lim)
    ax.set_xlabel("EMEP Tier 2 NH$_3$-N (kg N/ha)")
    ax.set_ylabel("ALFAM2 NH$_3$-N (kg N/ha)")
    _titles(ax, "ALFAM2 vs EMEP (1:1 reference)", subtitle)
    ax.legend(frameon=False, fontsize=9, loc="upper left")
    return fig


def fig_difference(df: pd.DataFrame, subtitle: str) -> plt.Figure:
    """C3 — (ALFAM2 - EMEP) per event, coloured by method (diverging at 0)."""
    d = df.sort_values("diff_kgNha").reset_index(drop=True)
    y = np.arange(len(d))
    colors = [_method_color(m) for m in d["app_mthd"]]

    fig, ax = plt.subplots(figsize=(8.5, max(4, 0.5 * len(d) + 1.5)))
    ax.barh(y, d["diff_kgNha"], color=colors)
    ax.axvline(0, color="#444444", lw=1)
    ax.set_yticks(y)
    ax.set_yticklabels(_event_labels(d))
    ax.set_xlabel("ALFAM2 − EMEP (kg N/ha)   [<0: ALFAM2 lower]")
    ax.set_ylabel("Event")
    _titles(ax, "Model difference per event (ALFAM2 − EMEP)", subtitle)
    handles = [plt.Line2D([0], [0], color=_method_color(m), lw=6,
                          label=_method_label(m)) for m in sorted(df["app_mthd"].unique())]
    ax.legend(handles=handles, frameon=False, fontsize=9, loc="lower right")
    return fig


def fig_pct_by_method(df: pd.DataFrame, subtitle: str) -> plt.Figure:
    """C4 — emission as % of TAN by method: EMEP (fixed) vs ALFAM2 (variable)."""
    methods = sorted(df["app_mthd"].unique())
    x = np.arange(len(methods))
    w = 0.38
    emep_means = [df.loc[df["app_mthd"] == m, "EMEP_pctTAN"].mean() for m in methods]
    alf_means = [df.loc[df["app_mthd"] == m, "ALFAM2_pctTAN"].mean() for m in methods]

    fig, ax = plt.subplots(figsize=(7.5, 5))
    ax.bar(x - w / 2, emep_means, width=w, color=EMEP_COLOR, label="EMEP Tier 2")
    ax.bar(x + w / 2, alf_means, width=w, color=ALFAM2_COLOR, label="ALFAM2")
    # Overlay individual events (deterministic spacing -> reproducible figure).
    for xi, m in zip(x, methods):
        vals = df.loc[df["app_mthd"] == m, "ALFAM2_pctTAN"].values
        k = len(vals)
        offs = np.linspace(-0.06, 0.06, k) if k > 1 else np.array([0.0])
        ax.scatter(xi + w / 2 + offs, vals,
                   color="#1B3A6B", s=22, zorder=3, edgecolor="white")
    ax.set_xticks(x)
    ax.set_xticklabels([_method_label(m) for m in methods])
    ax.set_ylabel("Emission (% of applied TAN)")
    _titles(ax, "Emission intensity by method: EMEP vs ALFAM2", subtitle)
    ax.legend(frameon=False, fontsize=9)
    return fig


FIGURES = (
    (fig_dumbbell,      "C1_dumbbell"),
    (fig_scatter,       "C2_scatter"),
    (fig_difference,    "C3_difference"),
    (fig_pct_by_method, "C4_pctTAN_by_method"),
)


# ─────────────────────────────────────────────────────────────────────────────
#  PER-PAIRING DRIVER
# ─────────────────────────────────────────────────────────────────────────────

def process_pairing(tag: str, emep_candidates: list[Path], alfam2_csv: Path,
                    subtitle: str, results_dir: Path) -> None:
    """Build the comparison table and figures for one pairing."""
    logger.info("Comparing pairing '%s'", tag)
    df = build_comparison(emep_candidates, alfam2_csv)

    out_dir = results_dir / f"comparison_{tag}"
    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_dir / f"comparison_{tag}.csv", index=False)

    # Console summary: totals over the common events, and mean ratio by method.
    tot_e, tot_a = df["EMEP_kgNha"].sum(), df["ALFAM2_kgNha"].sum()
    logger.info("  %d common events | EMEP total %.1f vs ALFAM2 total %.1f kg N/ha.",
                len(df), tot_e, tot_a)
    for m, sub in df.groupby("app_mthd"):
        logger.info("    method %-4s (n=%d): mean ALFAM2/EMEP ratio = %.2f",
                    m, len(sub), sub["ratio_A_over_E"].mean())

    for func, name in FIGURES:
        try:
            _save(func(df, subtitle), out_dir, name)
        except Exception as exc:  # noqa: BLE001 - isolate per-figure failures
            logger.error("    %s failed: %s", name, exc)


# ─────────────────────────────────────────────────────────────────────────────
#  CLI
# ─────────────────────────────────────────────────────────────────────────────

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare ALFAM2 vs EMEP Tier 2 per event, for the three pairings.",
    )
    parser.add_argument("--internship-dir", type=Path, default=INTERNSHIP_DIR,
                        help=f"Folder holding DB_plain_clean_EMEP (default: {INTERNSHIP_DIR}).")
    parser.add_argument("--results-dir", type=Path, default=RESULTS_DIR,
                        help=f"Folder with rotation/ALFAM2 outputs (default: {RESULTS_DIR}).")
    parser.add_argument("--verbose", action="store_true", help="Debug logging.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)-8s %(message)s",
    )

    pairings = build_pairings(args.internship_dir, args.results_dir)
    failures = 0
    for tag, emep_candidates, alfam2_csv, subtitle in pairings:
        try:
            process_pairing(tag, emep_candidates, alfam2_csv, subtitle, args.results_dir)
        except (FileNotFoundError, ValueError, KeyError) as exc:
            logger.error("Pairing '%s' failed: %s", tag, exc)
            failures += 1

    if failures:
        logger.error("Finished with %d pairing(s) failed.", failures)
        return 1
    logger.info("All comparisons done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
