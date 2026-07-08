#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
estimate_indirect_n2o.py
========================

Estimate INDIRECT N2O emissions from the NH3-N volatilization computed by the
EMEP Tier 2 inventory, following the IPCC 2019 Refinement (Vol. 4, Ch. 11).

Indirect N2O from atmospheric deposition of volatilized N:

    N2O-N (kg/ha) = N_volatilized (kg NH3-N/ha) x EF4

    N2O   (kg/ha) = N2O-N x 44/28                (N2O-N mass -> N2O mass)
    CO2eq (kg/ha) = N2O  x GWP100                (N2O -> CO2-equivalent)

    EF4  = 0.010 kg N2O-N per kg N volatilized   (range 0.002 - 0.018)
    GWP100(N2O) = 273  (IPCC AR6; AR5 = 265, AR4 = 298)

Notes
-----
* Using the MODELLED volatilization (EMEP) as the input to EF4 is a refinement
  over the IPCC Tier 1 default, which would apply a fixed FracGASF to applied N.
* Only the NH3 pathway is included here (EMEP output). The full IPCC term also
  adds NOx-N; this estimate is therefore the NH3-attributable indirect N2O.
* The uncertainty band comes from the EF4 range only (the dominant term).

Input: the EMEP per-event results produced by run_emep_tier2.py
    <file>_EMEP/events_emep.csv   (column NH3_emis_kgNha_EMEP)

Per dataset the script writes, to <RESULTS_DIR or next to input>:
    indirect_n2o_by_system.csv     per-system N2O-N, N2O, CO2eq (+ low/high)
    figures/N2O_indirect_by_system.<ext>

Input files are never modified.

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

INTERNSHIP_DIR: Path = Path(r"C:\Users\dzuni\OneDrive\Documentos\INTERNSHIP")
RESULTS_DIR: Path = INTERNSHIP_DIR / "Resultats_FINALES"

#: (label, events_emep.csv path, subtitle) per dataset.
def build_datasets(internship: Path, results: Path):
    return (
        ("full", internship / "DB_plain_clean_EMEP" / "events_emep.csv",
         "Indirect N2O from NH3 volatilization - full inventory (2018-2025)"),
        ("first_rotation", results / "DB_first_rotation_EMEP" / "events_emep.csv",
         "Indirect N2O - first rotation"),
        ("second_rotation", results / "DB_second_rotation_EMEP" / "events_emep.csv",
         "Indirect N2O - second rotation (COM/LOM)"),
    )

# IPCC parameters.
EF4: float = 0.010            # kg N2O-N per kg N volatilized (default)
EF4_LOW: float = 0.002        # lower bound of the EF4 range
EF4_HIGH: float = 0.018       # upper bound of the EF4 range
N2O_PER_N2ON: float = 44.0 / 28.0   # N2O-N mass -> N2O mass
GWP100_N2O: float = 273.0     # IPCC AR6 (AR5 = 265, AR4 = 298)

FIG_EXT: str = "png"

plt.rcParams.update({"font.size": 11, "axes.titlesize": 13,
                     "axes.titleweight": "bold", "figure.dpi": 150,
                     "axes.spines.top": False, "axes.spines.right": False})
BLUE, ORANGE, GREY = "#2F5597", "#C55A11", "#9AA0A6"
SYSTEM_ORDER = ("SCA", "GHG", "HYP", "CTR", "COM", "LI", "OF", "MF", "LOM")

logger = logging.getLogger("indirect_n2o")


# ─────────────────────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _ordered_systems(systems: list[str]) -> list[str]:
    known = [s for s in SYSTEM_ORDER if s in systems]
    return known + sorted(s for s in systems if s not in SYSTEM_ORDER)


def _first_col(df: pd.DataFrame, cands: list[str]) -> str:
    for c in cands:
        if c in df.columns:
            return c
    raise KeyError(f"None of {cands} present; have {list(df.columns)}")


def compute_indirect_n2o(nh3n_kgha: pd.Series) -> pd.DataFrame:
    """Apply EF4, molecular ratio and GWP to a per-system NH3-N series."""
    out = pd.DataFrame({"NH3N_kgha": nh3n_kgha})
    out["N2ON_kgha"] = out["NH3N_kgha"] * EF4
    out["N2O_kgha"] = out["N2ON_kgha"] * N2O_PER_N2ON
    out["CO2eq_kgha"] = out["N2O_kgha"] * GWP100_N2O
    # Uncertainty from the EF4 range (propagated linearly to CO2-eq).
    out["CO2eq_low"] = out["NH3N_kgha"] * EF4_LOW * N2O_PER_N2ON * GWP100_N2O
    out["CO2eq_high"] = out["NH3N_kgha"] * EF4_HIGH * N2O_PER_N2ON * GWP100_N2O
    return out.round(4)


# ─────────────────────────────────────────────────────────────────────────────
#  FIGURE
# ─────────────────────────────────────────────────────────────────────────────

def fig_by_system(res: pd.DataFrame, subtitle: str) -> plt.Figure:
    """Indirect-N2O CO2-equivalent by system, with the EF4 uncertainty band."""
    order = _ordered_systems(list(res.index))
    d = res.reindex(order)
    x = np.arange(len(d))
    # Asymmetric error bars from the EF4 range around the central estimate.
    lower = (d["CO2eq_kgha"] - d["CO2eq_low"]).clip(lower=0).values
    upper = (d["CO2eq_high"] - d["CO2eq_kgha"]).clip(lower=0).values

    fig, ax = plt.subplots(figsize=(8.5, 5))
    ax.bar(x, d["CO2eq_kgha"], color=BLUE, width=0.62)
    ax.errorbar(x, d["CO2eq_kgha"], yerr=[lower, upper], fmt="none",
                ecolor="#333333", elinewidth=1.2, capsize=4)
    for xi, v in zip(x, d["CO2eq_kgha"]):
        ax.text(xi, v, f"{v:.0f}", ha="center", va="bottom", fontsize=9)
    ax.set_xticks(x)
    ax.set_xticklabels(d.index)
    ax.set_ylabel("Indirect N$_2$O (kg CO$_2$-eq / ha)")
    ax.set_title("Indirect N$_2$O from NH$_3$ volatilization, by cropping system",
                 pad=26)
    ax.text(0.0, 1.015, subtitle, transform=ax.transAxes, fontsize=9,
            color=GREY, va="bottom")
    ax.text(0.99, 0.97,
            f"EF4 = {EF4} (range {EF4_LOW}-{EF4_HIGH})\nGWP100(N$_2$O) = {GWP100_N2O:.0f}",
            transform=ax.transAxes, ha="right", va="top", fontsize=8, color=GREY)
    return fig


# ─────────────────────────────────────────────────────────────────────────────
#  PER-DATASET DRIVER
# ─────────────────────────────────────────────────────────────────────────────

def process(label: str, events_csv: Path, subtitle: str) -> pd.Series | None:
    """Compute and write indirect-N2O results for one dataset. Returns totals."""
    if not events_csv.is_file():
        raise FileNotFoundError(f"{events_csv} not found. Run run_emep_tier2.py first.")

    df = pd.read_csv(events_csv)
    emis = _first_col(df, ["NH3_emis_kgNha_EMEP", "NH3_emis_kgNha"])
    by_system = df.groupby("Systeme")[emis].sum()

    res = compute_indirect_n2o(by_system)
    out_dir = events_csv.parent
    res.to_csv(out_dir / "indirect_n2o_by_system.csv")
    (out_dir / "figures").mkdir(exist_ok=True)
    fig = fig_by_system(res, subtitle)
    fig.savefig(out_dir / "figures" / f"N2O_indirect_by_system.{FIG_EXT}",
                bbox_inches="tight")
    plt.close(fig)

    tot = res[["NH3N_kgha", "N2ON_kgha", "N2O_kgha", "CO2eq_kgha"]].sum()
    logger.info("[%s] NH3-N %.1f -> N2O-N %.2f -> N2O %.2f -> %.0f kg CO2-eq/ha "
                "(range %.0f-%.0f)", label, tot["NH3N_kgha"], tot["N2ON_kgha"],
                tot["N2O_kgha"], tot["CO2eq_kgha"],
                res["CO2eq_low"].sum(), res["CO2eq_high"].sum())
    logger.info("       wrote indirect_n2o_by_system.csv + figure to %s", out_dir.name)
    tot["label"] = label
    return tot


# ─────────────────────────────────────────────────────────────────────────────
#  CLI
# ─────────────────────────────────────────────────────────────────────────────

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Estimate indirect N2O from EMEP NH3-N volatilization (IPCC EF4).",
    )
    parser.add_argument("--internship-dir", type=Path, default=INTERNSHIP_DIR)
    parser.add_argument("--results-dir", type=Path, default=RESULTS_DIR)
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)-8s %(message)s",
    )
    datasets = build_datasets(args.internship_dir, args.results_dir)
    failures = 0
    for label, csv, subtitle in datasets:
        try:
            process(label, csv, subtitle)
        except (FileNotFoundError, KeyError, ValueError) as exc:
            logger.error("[%s] %s", label, exc)
            failures += 1
    if failures:
        logger.error("Finished with %d dataset(s) failed.", failures)
        return 1
    logger.info("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
