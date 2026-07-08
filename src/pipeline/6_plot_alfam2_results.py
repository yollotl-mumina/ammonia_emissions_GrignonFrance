#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
plot_alfam2_results.py
======================

Generate the standard ALFAM2 figure set from the results produced by
``run_alfam2.R``. For each input file it reads two CSVs from RESULTS_DIR:

    <stem>_alfam2_hourly.csv     full hourly series with predicted emission
    <stem>_alfam2_by_event.csv   one row per event: final cumulative emission

and writes the figures to ``RESULTS_DIR/<stem>_alfam2_figures/``.

Figures (per file)
------------------
    A1  Cumulative NH3-N emission over time, one curve per event (by method)
    A2  Cumulative emission as % of applied TAN over time (by method)
    A3  Final NH3-N emission by event                       (kg NH3-N/ha)
    A4  Final emission intensity by application method       (% of TAN)
    A5  Final NH3-N emission by cropping system              (kg NH3-N/ha)

ALFAM2 applies only to liquid organic effluents, so application method
(bsth = trailing hose, bc = broadcast) is the key explanatory variable — the
technique sensitivity that EMEP's fixed 55%-of-TAN factor cannot capture.

All figure text is in English. Input CSVs are never modified.

>>> Run run_alfam2.R first to create the *_alfam2_*.csv files. <<<

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

#: Folder where run_alfam2.R wrote its CSV outputs.
RESULTS_DIR: Path = Path(r"C:\Users\dzuni\OneDrive\Documentos\INTERNSHIP\Resultats_FINALES")

#: File stems to plot, with a subtitle each (the *_alfam2_*.csv prefix).
DATASETS: tuple[tuple[str, str], ...] = (
    ("ALFAM2_entrada_horaria", "ALFAM2 (Set 3) — full set (2018–2025)"),
    ("ALFAM2_first_rotation",  "ALFAM2 (Set 3) — first rotation"),
    ("ALFAM2_second_rotation", "ALFAM2 (Set 3) — second rotation (COM/LOM)"),
)

FIG_EXT: str = "png"               # "png" or "pdf"

# Plot style (same palette as the EMEP figures).
plt.rcParams.update({"font.size": 11, "axes.titlesize": 13,
                     "axes.titleweight": "bold", "figure.dpi": 150,
                     "axes.spines.top": False, "axes.spines.right": False})
BLUE, ORANGE, GREY = "#2F5597", "#C55A11", "#9AA0A6"

# Application-method display names and colours.
METHOD_EN: dict[str, str] = {"bsth": "Trailing hose (bsth)", "bc": "Broadcast (bc)"}
METHOD_COLORS: dict[str, str] = {"bsth": BLUE, "bc": ORANGE}

# Product-category display names and colours (for the A4 method x category split).
CAT_SHORT: dict[str, str] = {"Lisier": "Slurry", "Digestat liquide": "Digestate"}
CAT_COLORS: dict[str, str] = {"Lisier": "#1F9E89", "Digestat liquide": "#4FB0AE"}
CAT_ORDER: tuple[str, ...] = ("Lisier", "Digestat liquide")

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

#: Preferred left-to-right system order (unknown systems are appended).
SYSTEM_ORDER: tuple[str, ...] = ("SCA", "GHG", "HYP", "CTR", "COM",
                                 "LI", "OF", "MF", "LOM")

logger = logging.getLogger("plot_alfam2")


# ─────────────────────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _first_col(df: pd.DataFrame, candidates: list[str]) -> str:
    """Return the first column in ``candidates`` present in ``df``.

    Raises
    ------
    KeyError
        If none of the candidate names is found.
    """
    for c in candidates:
        if c in df.columns:
            return c
    raise KeyError(f"None of the expected columns {candidates} is present; "
                   f"available: {list(df.columns)}")


def _method_label(code: str) -> str:
    """Human-readable label for an application-method code."""
    return METHOD_EN.get(str(code), str(code))


def _method_color(code: str) -> str:
    """Stable colour for an application-method code."""
    return METHOD_COLORS.get(str(code), GREY)


def _cat_short(cat: str) -> str:
    """Short English label for a product category."""
    return CAT_SHORT.get(str(cat), str(cat))


def _cat_color(cat: str) -> str:
    """Stable colour for a product category."""
    return CAT_COLORS.get(str(cat), GREY)


def _event_label(ev_id) -> str:
    """Custom display name for an event id, or the numeric id as fallback."""
    return EVENT_LABELS.get(int(ev_id), str(int(ev_id)))


def _ordered_systems(systems: list[str]) -> list[str]:
    """Return ``systems`` in the preferred order, appending any extras."""
    known = [s for s in SYSTEM_ORDER if s in systems]
    extra = sorted(s for s in systems if s not in SYSTEM_ORDER)
    return known + extra


def _titles(ax: plt.Axes, title: str, subtitle: str) -> None:
    """Bold title with a grey subtitle underneath, without overlap."""
    ax.set_title(title, pad=26)
    ax.text(0.0, 1.015, subtitle, transform=ax.transAxes,
            fontsize=9, color=GREY, va="bottom")


def _method_legend(ax: plt.Axes, methods: list[str],
                   counts: dict[str, int] | None = None) -> None:
    """Add a colour legend keyed by application method.

    If ``counts`` is given, the event count per method is appended as '(n=...)'.
    """
    def _lab(m: str) -> str:
        base = _method_label(m)
        return f"{base}  (n={counts[m]})" if counts and m in counts else base

    handles = [plt.Line2D([0], [0], color=_method_color(m), lw=3, label=_lab(m))
               for m in methods]
    ax.legend(handles=handles, frameon=False, fontsize=9)


def _save(fig: plt.Figure, fig_dir: Path, name: str) -> None:
    """Save and close a figure, creating the directory if needed."""
    fig_dir.mkdir(parents=True, exist_ok=True)
    path = fig_dir / f"{name}.{FIG_EXT}"
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    logger.info("    wrote %s", path.name)


def load_results(stem: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load the hourly and by-event CSVs for one dataset stem.

    Raises
    ------
    FileNotFoundError
        If either CSV is missing (run_alfam2.R was not run for that file).
    """
    hourly_path = RESULTS_DIR / f"{stem}_alfam2_hourly.csv"
    event_path = RESULTS_DIR / f"{stem}_alfam2_by_event.csv"
    for p in (hourly_path, event_path):
        if not p.is_file():
            raise FileNotFoundError(
                f"{p} not found. Run run_alfam2.R first to create it."
            )
    return pd.read_csv(hourly_path), pd.read_csv(event_path)


# ─────────────────────────────────────────────────────────────────────────────
#  FIGURES — hourly series
# ─────────────────────────────────────────────────────────────────────────────

def fig_cumulative_kg(hourly: pd.DataFrame, subtitle: str) -> plt.Figure:
    """A1 — cumulative NH3-N (kg N/ha) vs time, one curve per event."""
    t = "ct"
    e = _first_col(hourly, ["e", "emis", "cum.emis"])
    mcol = _first_col(hourly, ["app.mthd", "app_mthd"])

    fig, ax = plt.subplots(figsize=(8.5, 5))
    for ev_id, d in hourly.groupby("ID_evenement"):
        d = d.sort_values(t)
        method = d[mcol].iloc[0]
        ax.plot(d[t], d[e], color=_method_color(method), lw=1.6, alpha=0.9)
    ax.set_xlabel("Hours since application (ct)")
    ax.set_ylabel("Cumulative NH$_3$-N emission (kg N/ha)")
    _titles(ax, "ALFAM2 cumulative NH$_3$-N emission over time", subtitle)
    counts = hourly.groupby(mcol)["ID_evenement"].nunique().to_dict()
    _method_legend(ax, sorted(hourly[mcol].unique()), counts)
    return fig


def fig_cumulative_pct(hourly: pd.DataFrame, subtitle: str) -> plt.Figure:
    """A2 — cumulative emission as % of applied TAN vs time, per event."""
    t = "ct"
    mcol = _first_col(hourly, ["app.mthd", "app_mthd"])
    # Prefer the model's relative column; else derive from e / TAN.app.
    if any(c in hourly.columns for c in ("er", "e.rel")):
        rel = _first_col(hourly, ["er", "e.rel"])
        hourly = hourly.assign(_pct=100 * hourly[rel])
    else:
        e = _first_col(hourly, ["e", "emis", "cum.emis"])
        tan = _first_col(hourly, ["TAN.app", "TAN_app_kgNha"])
        hourly = hourly.assign(_pct=100 * hourly[e] / hourly[tan])

    fig, ax = plt.subplots(figsize=(8.5, 5))
    for ev_id, d in hourly.groupby("ID_evenement"):
        d = d.sort_values(t)
        ax.plot(d[t], d["_pct"], color=_method_color(d[mcol].iloc[0]),
                lw=1.6, alpha=0.9)
    ax.set_xlabel("Hours since application (ct)")
    ax.set_ylabel("Cumulative emission (% of applied TAN)")
    _titles(ax, "ALFAM2 cumulative emission as % of TAN", subtitle)
    counts = hourly.groupby(mcol)["ID_evenement"].nunique().to_dict()
    _method_legend(ax, sorted(hourly[mcol].unique()), counts)
    return fig


# ─────────────────────────────────────────────────────────────────────────────
#  FIGURES — by event
# ─────────────────────────────────────────────────────────────────────────────

def fig_emission_by_event(event: pd.DataFrame, subtitle: str) -> plt.Figure:
    """A3 — final NH3-N emission by event (kg N/ha), coloured by method."""
    mcol = _first_col(event, ["app_mthd", "app.mthd"])
    d = event.sort_values("NH3N_kgNha")
    labels = [_event_label(i) for i in d["ID_evenement"]]
    colors = [_method_color(m) for m in d[mcol]]

    fig, ax = plt.subplots(figsize=(9.5, 5))
    ax.barh(labels, d["NH3N_kgNha"], color=colors)
    for y, v in enumerate(d["NH3N_kgNha"]):
        ax.text(v, y, f" {v:.1f}", va="center", fontsize=9)
    ax.set_xlabel("Cumulative NH$_3$-N emission (kg N/ha)")
    ax.set_ylabel("Event")
    _titles(ax, "ALFAM2 final NH$_3$-N emission by event", subtitle)
    _method_legend(ax, sorted(event[mcol].unique()))
    return fig


def fig_intensity_by_method(event: pd.DataFrame, subtitle: str) -> plt.Figure:
    """A4 — final intensity (% of TAN) by application method, split by product.

    With few events per group a bar (mean) is misleading, so each group is shown
    as its individual events (points, evenly spaced) with a short line at the
    group mean. The product split is only applied when more than one product
    category is present; otherwise the figure collapses to a clean by-method
    view (e.g. the first rotation, which is slurry only).
    """
    mcol = _first_col(event, ["app_mthd", "app.mthd"])
    methods = sorted(event[mcol].unique())
    cats_present = [c for c in CAT_ORDER if c in set(event["Categorie"])]
    cats_present += sorted(set(event["Categorie"]) - set(CAT_ORDER))
    split_by_cat = len(cats_present) > 1

    # Build the ordered list of groups and their labels.
    groups: list[tuple[str, str | None]] = []
    if split_by_cat:
        for m in methods:
            for c in cats_present:
                if not event[(event[mcol] == m) & (event["Categorie"] == c)].empty:
                    groups.append((m, c))
    else:
        groups = [(m, None) for m in methods]

    x = np.arange(len(groups))
    labels = []
    fig, ax = plt.subplots(figsize=(max(7.0, 1.7 * len(groups) + 1.5), 5))
    for xi, (m, c) in zip(x, groups):
        mask = (event[mcol] == m)
        if c is not None:
            mask &= (event["Categorie"] == c)
        vals = event.loc[mask, "emis_pct_TAN"].values
        point_color = _cat_color(c) if c is not None else _cat_color(cats_present[0])
        labels.append(f"{_method_label(m)}\n{_cat_short(c)} (n={len(vals)})"
                      if c is not None else f"{_method_label(m)} (n={len(vals)})")

        # Evenly spaced (deterministic) horizontal offsets for the events.
        k = len(vals)
        offs = np.linspace(-0.18, 0.18, k) if k > 1 else np.array([0.0])
        ax.scatter(xi + offs, vals, color=point_color, s=55, zorder=3,
                   edgecolor="white")
        # Short line at the group mean.
        mean = float(np.mean(vals))
        ax.hlines(mean, xi - 0.28, xi + 0.28, color="#333333", lw=2, zorder=2)
        ax.text(xi + 0.32, mean, f"mean {mean:.0f}%", va="center", fontsize=8,
                color="#333333")

    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_xlim(-0.7, len(groups) - 0.3)
    ax.set_ylim(bottom=0)
    ax.set_ylabel("Emission intensity (% of applied TAN)")
    title = ("ALFAM2 emission intensity by method and product" if split_by_cat
             else "ALFAM2 emission intensity by application method")
    _titles(ax, title, subtitle)
    if split_by_cat:
        handles = [plt.Line2D([0], [0], marker="o", color="w", label=_cat_short(c),
                              markerfacecolor=_cat_color(c), markersize=9)
                   for c in cats_present]
        ax.legend(handles=handles, frameon=False, fontsize=9, title="Product")
    return fig


def fig_emission_by_system(event: pd.DataFrame, subtitle: str) -> plt.Figure:
    """A5 — final NH3-N by system, stacked by product category.

    Bars are kept thin and proportionate regardless of how many systems are
    present. If the dataset has a single system AND a single product category
    (e.g. MF in the first rotation, slurry only), a single bar would be
    uninformative, so the figure falls back to a per-event breakdown.
    """
    systems = _ordered_systems(list(event["Systeme"].unique()))
    cats_all = [c for c in CAT_ORDER if c in set(event["Categorie"])]
    cats_all += sorted(set(event["Categorie"]) - set(CAT_ORDER))

    # Degenerate case: one system, one category -> break down by event instead.
    if len(systems) == 1 and len(cats_all) == 1:
        d = event.sort_values("NH3N_kgNha", ascending=False).reset_index(drop=True)
        x = np.arange(len(d))
        colors = [_cat_color(c) for c in d["Categorie"]]
        fig, ax = plt.subplots(figsize=(max(6.0, 1.3 * len(d) + 2), 5))
        ax.bar(x, d["NH3N_kgNha"], width=0.6, color=colors)
        for xi, v in zip(x, d["NH3N_kgNha"]):
            ax.text(xi, v, f"{v:.1f}", ha="center", va="bottom", fontsize=9)
        ax.set_xticks(x)
        ax.set_xticklabels([_event_label(i) for i in d["ID_evenement"]],
                           rotation=30, ha="right")
        ax.set_xlim(-0.8, len(d) - 0.2)
        ax.set_ylabel("Cumulative NH$_3$-N emission (kg N/ha)")
        _titles(ax, f"ALFAM2 NH$_3$-N by event \u2014 single system: {systems[0]}",
                subtitle)
        return fig

    # General case: thin stacked bars by product category, per system.
    pivot = event.pivot_table(index="Systeme", columns="Categorie",
                              values="NH3N_kgNha", aggfunc="sum", fill_value=0.0)
    pivot = pivot.reindex(systems)
    x = np.arange(len(systems))

    fig, ax = plt.subplots(figsize=(max(6.0, 1.7 * len(systems) + 2.5), 5))
    bottom = np.zeros(len(systems))
    for c in cats_all:
        vals = pivot[c].values if c in pivot.columns else np.zeros(len(systems))
        ax.bar(x, vals, width=0.5, bottom=bottom, color=_cat_color(c),
               label=_cat_short(c))
        bottom += vals
    for xi, tot in zip(x, bottom):
        ax.text(xi, tot, f"{tot:.1f}", ha="center", va="bottom", fontsize=9)
    ax.set_xticks(x)
    ax.set_xticklabels(systems)
    ax.set_xlim(-0.8, len(systems) - 0.2)
    ax.set_ylabel("Cumulative NH$_3$-N emission (kg N/ha)")
    _titles(ax, "ALFAM2 NH$_3$-N by system, stacked by product", subtitle)
    ax.legend(frameon=False, fontsize=9, title="Product")
    return fig


# ─────────────────────────────────────────────────────────────────────────────
#  PER-FILE DRIVER
# ─────────────────────────────────────────────────────────────────────────────

#: (function, needs, output filename). ``needs`` selects which CSV to pass.
FIGURES = (
    (fig_cumulative_kg,      "hourly", "A1_cumulative_kg_over_time"),
    (fig_cumulative_pct,     "hourly", "A2_cumulative_pct_over_time"),
    (fig_emission_by_event,  "event",  "A3_emission_by_event"),
    (fig_intensity_by_method, "event", "A4_intensity_by_method"),
    (fig_emission_by_system, "event",  "A5_emission_by_system"),
)


def plot_dataset(stem: str, subtitle: str) -> None:
    """Produce the full ALFAM2 figure set for one dataset."""
    logger.info("Plotting %s", stem)
    hourly, event = load_results(stem)
    fig_dir = RESULTS_DIR / f"{stem}_alfam2_figures"

    for func, needs, name in FIGURES:
        try:
            fig = func(hourly if needs == "hourly" else event, subtitle)
            _save(fig, fig_dir, name)
        except Exception as exc:  # noqa: BLE001 - one bad figure must not stop the rest
            logger.error("    %s failed: %s", name, exc)


# ─────────────────────────────────────────────────────────────────────────────
#  CLI
# ─────────────────────────────────────────────────────────────────────────────

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot ALFAM2 NH3 results for the Trajectoire datasets.",
    )
    parser.add_argument(
        "--results-dir", type=Path, default=RESULTS_DIR,
        help=f"Folder with the *_alfam2_*.csv files (default: {RESULTS_DIR}).",
    )
    parser.add_argument(
        "--stems", type=str, nargs="+", default=[s for s, _ in DATASETS],
        help="Dataset stems to plot (default: the three ALFAM2 files).",
    )
    parser.add_argument("--verbose", action="store_true",
                        help="Enable debug-level logging.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    global RESULTS_DIR
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)-8s %(message)s",
    )
    RESULTS_DIR = args.results_dir
    subtitle_of = dict(DATASETS)

    failures = 0
    for stem in args.stems:
        try:
            plot_dataset(stem, subtitle_of.get(stem, "ALFAM2 (Set 3)"))
        except FileNotFoundError as exc:
            logger.error("%s", exc)
            failures += 1

    if failures:
        logger.error("Finished with %d dataset(s) failed.", failures)
        return 1
    logger.info("All figures generated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
