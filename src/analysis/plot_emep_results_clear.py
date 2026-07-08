#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
plot_emep_results_clear.py
==========================

Clarity-improved version of the EMEP Tier 2 figure set (F1-F5).

The aggregation logic is IDENTICAL to the original plot_emep_results.py, so
every number is unchanged. Only the *presentation* is improved:

  F1  headroom for labels, soft grid, scope + total in the subtitle.
  F2  same polish; a faint mean-intensity reference line.
  F3  colour scheme unified with F5, x-headroom so labels never clip.
  F4  the Entec effect is now QUANTIFIED on the plot: a red "-X kg" tag over
      every system whose value actually changed (others are annotated "no
      change"), so the figure can no longer be confused with the full-inventory
      83 kg quoted in the text.
  F5  the legend is moved OUTSIDE the plot area (it used to overlap the MF bar);
      a total label is printed on top of each stack.

Run
---
    python plot_emep_results_clear.py
      --input  <path>/events_emep.csv
      --outdir <path>/figures_clear
      --scope  "first rotation"      # free text shown in every subtitle

Defaults point at the two paths configured in the CONFIG block below; edit them
or pass the flags. Reusable for any rotation: just point --input at the
matching events_emep.csv (first / second / full inventory).
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# ─────────────────────────────────────────────────────────────────────────────
#  CONFIG — edit these two lines or override with --input / --outdir
# ─────────────────────────────────────────────────────────────────────────────
INPUT_CSV: Path = Path("events_emep.csv")
OUTPUT_DIR: Path = Path("figures_clear")
SCOPE: str = "first rotation"          # e.g. "first rotation" / "second rotation (COM/LOM)" / "full inventory (2018-2025)"
FIG_EXT: str = "png"

# ── style ────────────────────────────────────────────────────────────────────
plt.rcParams.update({
    "font.size": 12, "axes.titlesize": 15, "axes.titleweight": "bold",
    "figure.dpi": 160, "savefig.dpi": 160,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": "#E6E6E6", "grid.linewidth": 0.8,
})
BLUE, ORANGE, GREY, RED = "#2F5597", "#C55A11", "#9AA0A6", "#C0392B"

CAT_EN: dict[str, str] = {
    "Solution azotée (UAN)": "UAN solution", "Entec": "Entec (ASN)",
    "Urée": "Urea", "Thiosulfate": "Thiosulphate",
    "Ammonitrate": "Ammonium nitrate", "Lisier": "Cattle slurry",
    "Digestat liquide": "Liquid digestate", "Fumier solide": "Solid manure",
    "Autre organique": "Other organic",
    "Oligo/biostimulant": "Micronutrient/biostimulant", "Additif": "Additive",
}
CAT_COLORS: dict[str, str] = {
    "UAN solution": "#2F5597", "Entec (ASN)": "#C55A11", "Urea": "#7030A0",
    "Ammonium nitrate": "#548235", "Thiosulphate": "#BF9000",
    "Cattle slurry": "#1F9E89", "Liquid digestate": "#4FB0AE",
    "Solid manure": "#8C6D4F", "Other organic": "#C0504D",
    "Micronutrient/biostimulant": "#9AA0A6", "Additive": "#BFBFBF",
}
SYSTEM_ORDER = ("SCA", "GHG", "HYP", "CTR", "COM", "LI", "OF", "MF", "LOM")
SUBTITLE_BASE = "EMEP/EEA Guidebook 2023, Tier 2"


# ── helpers ──────────────────────────────────────────────────────────────────
def _ordered(systems: list[str]) -> list[str]:
    known = [s for s in SYSTEM_ORDER if s in systems]
    return known + sorted(s for s in systems if s not in SYSTEM_ORDER)


def _titles(ax, title: str, subtitle: str) -> None:
    ax.set_title(title, pad=30)
    ax.text(0.0, 1.02, subtitle, transform=ax.transAxes,
            fontsize=10, color=GREY, va="bottom")


def _save(fig, outdir: Path, name: str) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    fig.savefig(outdir / f"{name}.{FIG_EXT}", bbox_inches="tight")
    plt.close(fig)
    print(f"    wrote {name}.{FIG_EXT}")


def _grid_only_value_axis(ax, axis: str) -> None:
    """Show grid only on the value axis (y for vertical bars, x for horizontal)."""
    ax.grid(axis=axis, zorder=0)
    ax.set_axisbelow(True)


# ── figures ──────────────────────────────────────────────────────────────────
def fig_by_system(df, sub):
    s = df.groupby("Systeme")["NH3_emis_kgNha_EMEP"].sum().reindex(
        _ordered(list(df["Systeme"].unique())))
    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    _grid_only_value_axis(ax, "y")
    ax.bar(s.index, s.values, color=BLUE, zorder=3)
    for x, v in zip(s.index, s.values):
        ax.text(x, v + s.max() * 0.015, f"{v:.0f}", ha="center", va="bottom", fontsize=10)
    ax.set_ylim(0, s.max() * 1.12)
    ax.set_ylabel("NH$_3$-N emissions (kg N/ha)")
    _titles(ax, "Absolute NH$_3$-N emissions by cropping system", sub)
    return fig


def fig_intensity(df, sub):
    g = df.groupby("Systeme").agg(emis=("NH3_emis_kgNha_EMEP", "sum"),
                                  napp=("N_applied_kgNha", "sum"))
    g["pct"] = np.where(g["napp"] > 0, 100 * g["emis"] / g["napp"], np.nan)
    g = g.reindex(_ordered(list(g.index)))
    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    _grid_only_value_axis(ax, "y")
    ax.bar(g.index, g["pct"].values, color=ORANGE, zorder=3)
    for x, v in zip(g.index, g["pct"].values):
        if not np.isnan(v):
            ax.text(x, v + np.nanmax(g["pct"]) * 0.02, f"{v:.1f}%",
                    ha="center", va="bottom", fontsize=10)
    # faint reference: N-weighted mean intensity of the whole set
    mean_pct = 100 * g["emis"].sum() / g["napp"].sum()
    ax.axhline(mean_pct, color=GREY, ls="--", lw=1, zorder=2)
    ax.text(len(g) - 0.5, mean_pct, f"  set mean {mean_pct:.1f}%",
            color=GREY, va="bottom", ha="right", fontsize=9)
    ax.set_ylim(0, np.nanmax(g["pct"]) * 1.15)
    ax.set_ylabel("Intensity (% of applied N volatilized)")
    _titles(ax, "NH$_3$-N emission intensity by cropping system", sub)
    return fig


def fig_by_category(df, sub):
    s = df.groupby("Categorie")["NH3_emis_kgNha_EMEP"].sum().sort_values()
    s = s[s > 0]
    labels = [CAT_EN.get(c, c) for c in s.index]
    colors = [CAT_COLORS.get(l, BLUE) for l in labels]
    fig, ax = plt.subplots(figsize=(8.5, 5))
    _grid_only_value_axis(ax, "x")
    ax.barh(labels, s.values, color=colors, zorder=3)
    for y, v in enumerate(s.values):
        ax.text(v + s.max() * 0.01, y, f" {v:.0f}", va="center", fontsize=10)
    ax.set_xlim(0, s.max() * 1.10)
    ax.set_xlabel("NH$_3$-N emissions (kg N/ha)")
    _titles(ax, "NH$_3$-N emissions by product category", sub)
    return fig


def fig_baseline_vs_corrected(df, sub):
    g = df.groupby("Systeme").agg(baseline=("NH3_emis_kgNha_base", "sum"),
                                  corrected=("NH3_emis_kgNha_EMEP", "sum"))
    g = g.reindex(_ordered(list(g.index)))
    g["delta"] = g["corrected"] - g["baseline"]
    x = np.arange(len(g)); w = 0.4
    fig, ax = plt.subplots(figsize=(9.5, 5))
    _grid_only_value_axis(ax, "y")
    ax.bar(x - w / 2, g["baseline"], width=w, label="Baseline (Entec as AS)",
           color=GREY, zorder=3)
    ax.bar(x + w / 2, g["corrected"], width=w, label="Corrected (Entec as ASN)",
           color=BLUE, zorder=3)
    top = float(g[["baseline", "corrected"]].values.max())
    # Quantify the effect over each affected system.
    for xi, (_, r) in zip(x, g.iterrows()):
        if abs(r["delta"]) >= 0.05:
            ymax = max(r["baseline"], r["corrected"])
            ax.annotate("", xy=(xi + w / 2, r["corrected"]),
                        xytext=(xi - w / 2, r["baseline"]),
                        arrowprops=dict(arrowstyle="->", color=RED, lw=1.6))
            ax.text(xi, ymax + top * 0.03, f"{r['delta']:+.0f} kg",
                    ha="center", va="bottom", color=RED, fontweight="bold",
                    fontsize=10)
    ax.set_ylim(0, top * 1.16)
    ax.set_xticks(x); ax.set_xticklabels(g.index)
    ax.set_ylabel("NH$_3$-N emissions (kg N/ha)")
    _titles(ax, "Effect of the Entec correction, by cropping system", sub)
    changed = ", ".join(g.index[abs(g["delta"]) >= 0.05])
    note = (f"Only {changed} changes; all other systems are identical "
            f"(no Entec applied)." if changed else "No system changed.")
    ax.text(0.0, -0.16, note, transform=ax.transAxes, fontsize=9, color=GREY)
    ax.legend(frameon=False, fontsize=10, loc="upper left",
              bbox_to_anchor=(0.0, -0.05), ncol=2)
    return fig


def fig_stacked(df, sub):
    d = df.copy()
    d["Cat_EN"] = d["Categorie"].map(lambda c: CAT_EN.get(c, c))
    pivot = d.pivot_table(index="Systeme", columns="Cat_EN",
                          values="NH3_emis_kgNha_EMEP", aggfunc="sum",
                          fill_value=0.0).reindex(_ordered(list(d["Systeme"].unique())))
    totals = pivot.sum().sort_values(ascending=False)
    cats = [c for c in totals.index if totals[c] > 0]

    fig, ax = plt.subplots(figsize=(10.5, 5.2))
    _grid_only_value_axis(ax, "y")
    bottom = np.zeros(len(pivot))
    for cat in cats:
        vals = pivot[cat].values
        ax.bar(pivot.index, vals, bottom=bottom,
               color=CAT_COLORS.get(cat, BLUE), label=cat, zorder=3)
        bottom += vals
    stack_tot = pivot[cats].sum(axis=1).values
    for xi, t in enumerate(stack_tot):
        if t > 0:
            ax.text(xi, t + stack_tot.max() * 0.015, f"{t:.0f}",
                    ha="center", va="bottom", fontsize=9, color="#333333")
    ax.set_ylim(0, stack_tot.max() * 1.12)
    ax.set_ylabel("NH$_3$-N emissions (kg N/ha)")
    _titles(ax, "NH$_3$-N emissions by system, stacked by product category", sub)
    # legend OUTSIDE the plotting area so it never overlaps a bar
    ax.legend(frameon=False, fontsize=9, loc="upper left",
              bbox_to_anchor=(1.01, 1.0), title="Product")
    return fig


FIGURES = (
    (fig_by_system,             "F1_emissions_by_system"),
    (fig_intensity,             "F2_intensity_by_system"),
    (fig_by_category,           "F3_emissions_by_category"),
    (fig_baseline_vs_corrected, "F4_baseline_vs_corrected"),
    (fig_stacked,               "F5_stacked_by_category"),
)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, default=INPUT_CSV)
    p.add_argument("--outdir", type=Path, default=OUTPUT_DIR)
    p.add_argument("--scope", type=str, default=SCOPE)
    a = p.parse_args()

    df = pd.read_csv(a.input)
    total = df["NH3_emis_kgNha_EMEP"].sum()
    n = len(df)
    subtitle = (f"{SUBTITLE_BASE} \u2014 {a.scope}  ·  "
                f"{total:.0f} kg NH$_3$-N/ha across {n} events")
    print(f"Loaded {n} events, total {total:.1f} kg NH3-N/ha  ->  {a.outdir}")
    for func, name in FIGURES:
        try:
            _save(func(df, subtitle), a.outdir, name)
        except Exception as exc:
            print(f"    {name} FAILED: {exc}")


if __name__ == "__main__":
    main()
