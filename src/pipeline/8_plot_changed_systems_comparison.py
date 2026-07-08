#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
plot_changed_systems_comparison.py
==================================

Plot the ALFAM2 vs EMEP Tier 2 comparison EXCLUSIVELY for the cropping systems
that were replaced between the first and second rotation:

    CTR  -> COM   (Control            -> Crop-oriented methanization)
    MF   -> LOM   (Mixed farming      -> Livestock-oriented methanization)

Input: the per-event comparison tables produced by compare_alfam2_emep.py
    <RESULTS_DIR>/comparison_first_rotation/comparison_first_rotation.csv
    <RESULTS_DIR>/comparison_second_rotation/comparison_second_rotation.csv

Each event is tagged with its lineage (CTR->COM or MF->LOM) and its rotation
(R1 or R2), then filtered to the two transitioning lineages. ALFAM2 only models
liquid organic effluents, so only these systems (which receive slurry/digestate)
appear in the comparison at all.

Figures (written to <RESULTS_DIR>/comparison_changed_systems/)
--------------------------------------------------------------
    T1_dumbbell_by_lineage   per-event EMEP vs ALFAM2, grouped by lineage/rotation
    T2_totals_by_group       total NH3-N by lineage x rotation, EMEP vs ALFAM2
    T3_pctTAN_by_group       emission as % of TAN by lineage x rotation, both models
    T4_scatter               EMEP vs ALFAM2 (colour=lineage, marker=rotation)

Note: CTR->COM usually has no first-rotation events here, because the control
system received no liquid organic effluent before the methanization change.
That absence is shown, not hidden.

Input CSVs are never modified.

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

RESULTS_DIR: Path = Path(r"C:\Users\dzuni\OneDrive\Documentos\INTERNSHIP\Resultats_FINALES")
FIG_EXT: str = "png"

# Map each system code to its transition lineage. Systems not listed here are
# dropped (they did not change between rotations / have no ALFAM2 events).
LINEAGE: dict[str, str] = {
    "CTR": "CTR \u2192 COM", "COM": "CTR \u2192 COM",
    "MF":  "MF \u2192 LOM",  "LOM": "MF \u2192 LOM",
}
#: Left-to-right lineage order (MF->LOM has both rotations, shown first).
LINEAGE_ORDER: tuple[str, ...] = ("MF \u2192 LOM", "CTR \u2192 COM")

# Plot style (shared palette).
plt.rcParams.update({"font.size": 11, "axes.titlesize": 13,
                     "axes.titleweight": "bold", "figure.dpi": 150,
                     "axes.spines.top": False, "axes.spines.right": False})
BLUE, ORANGE, GREY = "#2F5597", "#C55A11", "#9AA0A6"
EMEP_COLOR, ALFAM2_COLOR = GREY, BLUE
LINEAGE_COLORS: dict[str, str] = {"MF \u2192 LOM": "#1F9E89", "CTR \u2192 COM": "#7030A0"}
ROTATION_MARKERS: dict[str, str] = {"R1": "o", "R2": "s"}

# Product-category encoding (the new separation dimension).
CAT_SHORT: dict[str, str] = {"Lisier": "Slurry", "Digestat liquide": "Digestate"}
CAT_COLORS: dict[str, str] = {"Lisier": "#1F9E89", "Digestat liquide": "#4FB0AE"}
#: Category order (slurry first, digestate second).
CAT_ORDER: tuple[str, ...] = ("Lisier", "Digestat liquide")

SUBTITLE: str = "Transitioning systems only \u2014 ALFAM2 vs EMEP Tier 2"

# Custom per-event display names (by ID_evenement). Events not listed fall back
# to their numeric id. Edit here to rename events across the figures.
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


def _event_label(ev_id) -> str:
    """Custom display name for an event id, or the numeric id as fallback."""
    return EVENT_LABELS.get(int(ev_id), str(int(ev_id)))

logger = logging.getLogger("plot_changed_systems")


# ─────────────────────────────────────────────────────────────────────────────
#  LOAD & LABEL
# ─────────────────────────────────────────────────────────────────────────────

def _load_one(path: Path, rotation: str) -> pd.DataFrame:
    """Load one comparison CSV and tag it with its rotation label."""
    if not path.is_file():
        raise FileNotFoundError(
            f"{path} not found. Run compare_alfam2_emep.py first."
        )
    df = pd.read_csv(path)
    df["rotation"] = rotation
    return df


def load_changed_systems(results_dir: Path) -> pd.DataFrame:
    """Load both rotations, tag lineage/rotation, keep only changed systems.

    Raises
    ------
    FileNotFoundError
        If either comparison CSV is missing.
    ValueError
        If no events remain after filtering to the transitioning lineages.
    """
    r1 = _load_one(results_dir / "comparison_first_rotation" /
                   "comparison_first_rotation.csv", "R1")
    r2 = _load_one(results_dir / "comparison_second_rotation" /
                   "comparison_second_rotation.csv", "R2")
    both = pd.concat([r1, r2], ignore_index=True)

    both["lineage"] = both["Systeme"].map(LINEAGE)
    keep = both[both["lineage"].notna()].copy()
    if keep.empty:
        raise ValueError("No events for the transitioning systems "
                         "(CTR/COM, MF/LOM) in the comparison tables.")

    logger.info("Kept %d event(s) across the transitioning lineages.", len(keep))
    for (lin, rot), sub in keep.groupby(["lineage", "rotation"]):
        logger.info("  %-12s %s: %d event(s).", lin, rot, len(sub))
    return keep


# ─────────────────────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _titles(ax: plt.Axes, title: str, subtitle: str = SUBTITLE) -> None:
    ax.set_title(title, pad=26)
    ax.text(0.0, 1.015, subtitle, transform=ax.transAxes,
            fontsize=9, color=GREY, va="bottom")


def _save(fig: plt.Figure, fig_dir: Path, name: str) -> None:
    fig_dir.mkdir(parents=True, exist_ok=True)
    path = fig_dir / f"{name}.{FIG_EXT}"
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    logger.info("    wrote %s", path.name)


def _present_lineages(df: pd.DataFrame) -> list[str]:
    """Lineages present in the data, in the preferred order."""
    present = set(df["lineage"])
    return [l for l in LINEAGE_ORDER if l in present]


def _present_groups(df: pd.DataFrame) -> list[tuple[str, str]]:
    """(lineage, rotation) groups present, ordered lineage-major then R1, R2."""
    groups = []
    for lin in _present_lineages(df):
        for rot in ("R1", "R2"):
            if not df[(df["lineage"] == lin) & (df["rotation"] == rot)].empty:
                groups.append((lin, rot))
    return groups


def _cat_short(cat: str) -> str:
    """Short English label for a product category."""
    return CAT_SHORT.get(str(cat), str(cat))


def _cat_color(cat: str) -> str:
    """Stable colour for a product category."""
    return CAT_COLORS.get(str(cat), GREY)


def _present_cat_groups(df: pd.DataFrame) -> list[tuple[str, str, str]]:
    """(lineage, rotation, category) groups present, in a stable order.

    Ordered lineage-major, then R1 before R2, then by the category order.
    """
    groups = []
    for lin in _present_lineages(df):
        for rot in ("R1", "R2"):
            for cat in CAT_ORDER:
                sub = df[(df["lineage"] == lin) & (df["rotation"] == rot)
                         & (df["Categorie"] == cat)]
                if not sub.empty:
                    groups.append((lin, rot, cat))
            # Append any category not in CAT_ORDER (defensive).
            extra = df[(df["lineage"] == lin) & (df["rotation"] == rot)
                       & (~df["Categorie"].isin(CAT_ORDER))]
            for cat in sorted(extra["Categorie"].unique()):
                groups.append((lin, rot, cat))
    return groups


# ─────────────────────────────────────────────────────────────────────────────
#  FIGURES
# ─────────────────────────────────────────────────────────────────────────────

def fig_dumbbell_by_lineage(df: pd.DataFrame) -> plt.Figure:
    """T1 — per-event EMEP vs ALFAM2, ordered by lineage, rotation, category.

    The connector line is coloured by product category (slurry vs digestate);
    the markers keep the model colours (EMEP grey, ALFAM2 blue).
    """
    # Order rows: lineage-major, then R1 before R2, then by category, then value.
    order_key = []
    for lin in _present_lineages(df):
        for rot in ("R1", "R2"):
            for cat in CAT_ORDER:
                sub = df[(df["lineage"] == lin) & (df["rotation"] == rot)
                         & (df["Categorie"] == cat)]
                if not sub.empty:
                    order_key.append(sub.sort_values("EMEP_kgNha"))
    d = pd.concat(order_key, ignore_index=True)
    y = np.arange(len(d))
    labels = [_event_label(i) for i in d["ID_evenement"]]

    fig, ax = plt.subplots(figsize=(9.5, max(4, 0.55 * len(d) + 1.5)))
    # Light background bands per lineage block.
    start = 0
    for lin in _present_lineages(d):
        n = int((d["lineage"] == lin).sum())
        ax.axhspan(start - 0.5, start + n - 0.5,
                   color=LINEAGE_COLORS.get(lin, GREY), alpha=0.06)
        ax.text(0.005, (start + start + n - 1) / 2, lin,
                transform=ax.get_yaxis_transform(),
                rotation=90, va="center", ha="right", fontsize=9,
                color=LINEAGE_COLORS.get(lin, GREY), fontweight="bold")
        start += n

    # Connector coloured by product category.
    for yi, (_, row) in zip(y, d.iterrows()):
        ax.hlines(yi, row["EMEP_kgNha"], row["ALFAM2_kgNha"],
                  color=_cat_color(row["Categorie"]), lw=2.5, alpha=0.8, zorder=1)
    ax.scatter(d["EMEP_kgNha"], y, color=EMEP_COLOR, s=55, zorder=2, label="EMEP Tier 2")
    ax.scatter(d["ALFAM2_kgNha"], y, color=ALFAM2_COLOR, s=55, zorder=2, label="ALFAM2")
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.set_xlabel("NH$_3$-N emission (kg N/ha)")
    ax.set_ylabel("Event")
    _titles(ax, "EMEP vs ALFAM2 \u2014 transitioning systems")

    # Two legends: models (markers) and product categories (connector colours).
    model_handles = [plt.Line2D([0], [0], marker="o", color="w", label=lab,
                                markerfacecolor=col, markersize=9)
                     for lab, col in [("EMEP Tier 2", EMEP_COLOR), ("ALFAM2", ALFAM2_COLOR)]]
    cat_handles = [plt.Line2D([0], [0], color=_cat_color(c), lw=3, label=_cat_short(c))
                   for c in CAT_ORDER if c in set(d["Categorie"])]
    leg1 = ax.legend(handles=model_handles, frameon=False, fontsize=9,
                     loc="lower right", title="Model")
    ax.add_artist(leg1)
    ax.legend(handles=cat_handles, frameon=False, fontsize=9,
              loc="lower right", bbox_to_anchor=(1.0, 0.18), title="Product")
    return fig


def fig_totals_by_group(df: pd.DataFrame) -> plt.Figure:
    """T2 — total NH3-N by (lineage, rotation, category): EMEP vs ALFAM2."""
    groups = _present_cat_groups(df)

    def _mask(l, r, c):
        return (df.lineage == l) & (df.rotation == r) & (df.Categorie == c)

    ns = [int(_mask(l, r, c).sum()) for l, r, c in groups]
    glabels = [f"{lin}\n{rot} \u00b7 {_cat_short(cat)}\n(n={n})"
               for (lin, rot, cat), n in zip(groups, ns)]
    emep = [df[_mask(l, r, c)]["EMEP_kgNha"].sum() for l, r, c in groups]
    alf = [df[_mask(l, r, c)]["ALFAM2_kgNha"].sum() for l, r, c in groups]
    x = np.arange(len(groups))
    w = 0.38

    fig, ax = plt.subplots(figsize=(max(8.5, 1.7 * len(groups) + 2), 5))
    b1 = ax.bar(x - w / 2, emep, width=w, color=EMEP_COLOR, label="EMEP Tier 2")
    b2 = ax.bar(x + w / 2, alf, width=w, color=ALFAM2_COLOR, label="ALFAM2")
    for rect in list(b1) + list(b2):
        ax.text(rect.get_x() + rect.get_width() / 2, rect.get_height(),
                f"{rect.get_height():.0f}", ha="center", va="bottom", fontsize=8)
    ax.set_xticks(x)
    ax.set_xticklabels(glabels)
    ax.set_ylabel("Total NH$_3$-N emission (kg N/ha)")
    _titles(ax, "Total NH$_3$-N by transition group and product")
    ax.legend(frameon=False, fontsize=9)
    return fig


def fig_pct_by_group(df: pd.DataFrame) -> plt.Figure:
    """T3 — emission as % of TAN by (lineage, rotation, category)."""
    groups = _present_cat_groups(df)

    def _mask(l, r, c):
        return (df.lineage == l) & (df.rotation == r) & (df.Categorie == c)

    ns = [int(_mask(l, r, c).sum()) for l, r, c in groups]
    glabels = [f"{lin}\n{rot} \u00b7 {_cat_short(cat)}\n(n={n})"
               for (lin, rot, cat), n in zip(groups, ns)]
    emep = [df[_mask(l, r, c)]["EMEP_pctTAN"].mean() for l, r, c in groups]
    alf = [df[_mask(l, r, c)]["ALFAM2_pctTAN"].mean() for l, r, c in groups]
    x = np.arange(len(groups))
    w = 0.38

    fig, ax = plt.subplots(figsize=(max(8.5, 1.7 * len(groups) + 2), 5))
    ax.bar(x - w / 2, emep, width=w, color=EMEP_COLOR, label="EMEP Tier 2")
    ax.bar(x + w / 2, alf, width=w, color=ALFAM2_COLOR, label="ALFAM2")
    # Overlay individual ALFAM2 events (deterministic spacing -> reproducible).
    for xi, (l, r, c) in zip(x, groups):
        vals = df[_mask(l, r, c)]["ALFAM2_pctTAN"].values
        k = len(vals)
        offs = np.linspace(-0.06, 0.06, k) if k > 1 else np.array([0.0])
        ax.scatter(xi + w / 2 + offs, vals,
                   color="#1B3A6B", s=22, zorder=3, edgecolor="white")
    ax.set_xticks(x)
    ax.set_xticklabels(glabels)
    ax.set_ylabel("Emission (% of applied TAN)")
    _titles(ax, "Emission intensity by transition group and product")
    ax.legend(frameon=False, fontsize=9)
    return fig


def fig_scatter(df: pd.DataFrame) -> plt.Figure:
    """T4 — EMEP vs ALFAM2 (colour=product category, marker=rotation), 1:1 line."""
    lim = float(np.nanmax([df["EMEP_kgNha"].max(), df["ALFAM2_kgNha"].max()])) * 1.1
    lim = max(lim, 1.0)

    fig, ax = plt.subplots(figsize=(6.8, 6.8))
    ax.plot([0, lim], [0, lim], color=GREY, ls="--", lw=1, label="1:1 line")
    for cat in CAT_ORDER:
        for rot in ("R1", "R2"):
            sub = df[(df.Categorie == cat) & (df.rotation == rot)]
            if sub.empty:
                continue
            ax.scatter(sub["EMEP_kgNha"], sub["ALFAM2_kgNha"],
                       color=_cat_color(cat),
                       marker=ROTATION_MARKERS.get(rot, "o"),
                       s=70, edgecolor="white",
                       label=f"{_cat_short(cat)} ({rot})", zorder=3)
    ax.set_xlim(0, lim)
    ax.set_ylim(0, lim)
    ax.set_xlabel("EMEP Tier 2 NH$_3$-N (kg N/ha)")
    ax.set_ylabel("ALFAM2 NH$_3$-N (kg N/ha)")
    _titles(ax, "ALFAM2 vs EMEP \u2014 by product category")
    ax.legend(frameon=False, fontsize=8.5, loc="upper left")
    return fig


FIGURES = (
    (fig_dumbbell_by_lineage, "T1_dumbbell_by_lineage"),
    (fig_totals_by_group,     "T2_totals_by_group"),
    (fig_pct_by_group,        "T3_pctTAN_by_group"),
    (fig_scatter,             "T4_scatter"),
)


# ─────────────────────────────────────────────────────────────────────────────
#  DRIVER & CLI
# ─────────────────────────────────────────────────────────────────────────────

def run(results_dir: Path) -> None:
    """Load, filter to changed systems, and write the focused figure set."""
    df = load_changed_systems(results_dir)
    out_dir = results_dir / "comparison_changed_systems"
    out_dir.mkdir(parents=True, exist_ok=True)
    df.sort_values(["lineage", "rotation", "ID_evenement"]).to_csv(
        out_dir / "comparison_changed_systems.csv", index=False)

    for func, name in FIGURES:
        try:
            _save(func(df), out_dir, name)
        except Exception as exc:  # noqa: BLE001 - isolate per-figure failures
            logger.error("    %s failed: %s", name, exc)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot the ALFAM2 vs EMEP comparison only for the systems "
                    "that changed between rotations (CTR->COM, MF->LOM).",
    )
    parser.add_argument("--results-dir", type=Path, default=RESULTS_DIR,
                        help=f"Folder with the comparison_* outputs (default: {RESULTS_DIR}).")
    parser.add_argument("--verbose", action="store_true", help="Debug logging.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)-8s %(message)s",
    )
    try:
        run(args.results_dir)
    except (FileNotFoundError, ValueError) as exc:
        logger.error("%s", exc)
        return 1
    logger.info("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
