#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sensitivity_and_indirect_n2o.py
===============================

Two analyses on one EMEP Tier 2 per-event file (events_emep.csv):

  A. INDIRECT N2O (IPCC 2019, EF4 pathway)
       CO2eq = NH3-N * EF4 * (44/28) * GWP100(N2O)
     Reported per system and as a total, with the EF4 uncertainty band.
     Method and constants match 9_estimate_indirect_n2o.py.

  B. SENSITIVITY ANALYSIS
       B1  Structural toggle  : Entec baseline (as AS) vs corrected (as ASN),
                                using the two emission columns already in the file.
       B2  NH3 emission-factor: one-at-a-time (OAT) +/-30% per product category
                                -> tornado of the change in the total inventory.
                                (Scaling a category's EF by k scales its emission
                                 by k, so DELTA_total = +/-0.30 * category total.)
       B3  N2O EF4 range       : low / central / high total CO2eq.
       B4  GWP choice          : AR6 (273) / AR5 (265) / AR4 (298).

Outputs (to --outdir):
    indirect_n2o_by_system.csv
    sensitivity_ef_tornado.csv
    sensitivity_summary.csv
    N2O_indirect_by_system.png
    sensitivity_ef_tornado.png

Run
---
    python sensitivity_and_indirect_n2o.py
      --input <path>/events_emep.csv
      --outdir <path>/sensitivity_n2o
      --scope "first rotation"

Reusable for any rotation: point --input at the matching events_emep.csv.
The tornado OAT range is illustrative (+/-30%); change --ef-perturb if needed.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# ── constants (identical to 9_estimate_indirect_n2o.py) ──────────────────────
EF4, EF4_LOW, EF4_HIGH = 0.010, 0.002, 0.018      # kg N2O-N per kg N volatilized
N2O_PER_N2ON = 44.0 / 28.0                          # N2O-N mass -> N2O mass
GWP = {"AR6 (273)": 273.0, "AR5 (265)": 265.0, "AR4 (298)": 298.0}
GWP_DEFAULT = 273.0

# ── style ────────────────────────────────────────────────────────────────────
plt.rcParams.update({
    "font.size": 12, "axes.titlesize": 15, "axes.titleweight": "bold",
    "figure.dpi": 160, "savefig.dpi": 160,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": "#E6E6E6", "grid.linewidth": 0.8,
})
BLUE, ORANGE, GREY, RED = "#2F5597", "#C55A11", "#9AA0A6", "#C0392B"
SYSTEM_ORDER = ("SCA", "GHG", "HYP", "CTR", "COM", "LI", "OF", "MF", "LOM")
CAT_EN = {
    "Solution azotée (UAN)": "UAN solution", "Entec": "Entec (ASN)",
    "Urée": "Urea", "Thiosulfate": "Thiosulphate", "Ammonitrate": "Ammonium nitrate",
    "Lisier": "Cattle slurry", "Digestat liquide": "Liquid digestate",
    "Fumier solide": "Solid manure", "Autre organique": "Other organic",
    "Oligo/biostimulant": "Micronutrient/biostimulant", "Additif": "Additive",
}


def _ordered(systems):
    known = [s for s in SYSTEM_ORDER if s in systems]
    return known + sorted(s for s in systems if s not in SYSTEM_ORDER)


def _titles(ax, title, subtitle):
    ax.set_title(title, pad=30)
    ax.text(0.0, 1.02, subtitle, transform=ax.transAxes, fontsize=10,
            color=GREY, va="bottom")


# ── A. indirect N2O ──────────────────────────────────────────────────────────
def indirect_n2o(nh3n: pd.Series) -> pd.DataFrame:
    out = pd.DataFrame({"NH3N_kgha": nh3n})
    out["N2ON_kgha"] = out["NH3N_kgha"] * EF4
    out["N2O_kgha"] = out["N2ON_kgha"] * N2O_PER_N2ON
    out["CO2eq_kgha"] = out["N2O_kgha"] * GWP_DEFAULT
    out["CO2eq_low"] = out["NH3N_kgha"] * EF4_LOW * N2O_PER_N2ON * GWP_DEFAULT
    out["CO2eq_high"] = out["NH3N_kgha"] * EF4_HIGH * N2O_PER_N2ON * GWP_DEFAULT
    return out


def fig_n2o_by_system(res: pd.DataFrame, subtitle: str):
    d = res.reindex(_ordered(list(res.index)))
    x = np.arange(len(d))
    lower = (d["CO2eq_kgha"] - d["CO2eq_low"]).clip(lower=0).values
    upper = (d["CO2eq_high"] - d["CO2eq_kgha"]).clip(lower=0).values
    fig, ax = plt.subplots(figsize=(9, 5.2))
    ax.grid(axis="y"); ax.set_axisbelow(True)
    ax.bar(x, d["CO2eq_kgha"], color=BLUE, width=0.62, zorder=3)
    ax.errorbar(x, d["CO2eq_kgha"], yerr=[lower, upper], fmt="none",
                ecolor="#333333", elinewidth=1.2, capsize=4, zorder=4)
    for xi, v in zip(x, d["CO2eq_kgha"]):
        ax.text(xi, d["CO2eq_high"].iloc[xi] + d["CO2eq_high"].max() * 0.02,
                f"{v:.0f}", ha="center", va="bottom", fontsize=9)
    ax.set_ylim(0, d["CO2eq_high"].max() * 1.15)
    ax.set_xticks(x); ax.set_xticklabels(d.index)
    ax.set_ylabel("Indirect N$_2$O (kg CO$_2$-eq / ha)")
    _titles(ax, "Indirect N$_2$O from NH$_3$ volatilization, by system", subtitle)
    ax.text(0.99, 0.97, f"EF4 = {EF4} (range {EF4_LOW}-{EF4_HIGH})\n"
            f"GWP100(N$_2$O) = {GWP_DEFAULT:.0f}  (error bars = EF4 range)",
            transform=ax.transAxes, ha="right", va="top", fontsize=9, color=GREY)
    return fig


# ── B. sensitivity ───────────────────────────────────────────────────────────
def ef_tornado(df: pd.DataFrame, perturb: float) -> pd.DataFrame:
    by_cat = df.groupby("Categorie")["NH3_emis_kgNha_EMEP"].sum()
    by_cat = by_cat[by_cat > 0].sort_values(ascending=False)
    rows = []
    for cat, emis in by_cat.items():
        rows.append({"category": CAT_EN.get(cat, cat),
                     "emission_kgha": emis,
                     "delta_minus": -perturb * emis,
                     "delta_plus": +perturb * emis})
    return pd.DataFrame(rows)


def fig_tornado(tor: pd.DataFrame, total: float, perturb: float, subtitle: str):
    t = tor.sort_values("emission_kgha")           # smallest at bottom
    y = np.arange(len(t))
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.grid(axis="x"); ax.set_axisbelow(True)
    ax.barh(y, t["delta_plus"], color=ORANGE, zorder=3, label=f"+{perturb:.0%} EF")
    ax.barh(y, t["delta_minus"], color=BLUE, zorder=3, label=f"-{perturb:.0%} EF")
    for yi, row in zip(y, t.itertuples()):
        ax.text(row.delta_plus, yi, f"  {row.delta_plus:+.0f}", va="center",
                ha="left", fontsize=9, color=ORANGE)
        ax.text(row.delta_minus, yi, f"{row.delta_minus:+.0f}  ", va="center",
                ha="right", fontsize=9, color=BLUE)
    ax.axvline(0, color="#333333", lw=1)
    ax.set_yticks(y); ax.set_yticklabels(t["category"])
    ax.set_xlabel("Change in total inventory NH$_3$-N (kg N/ha)")
    _titles(ax, f"NH$_3$ emission-factor sensitivity (OAT, \u00b1{perturb:.0%})", subtitle)
    ax.text(0.99, 0.05, f"Baseline total = {total:.0f} kg NH$_3$-N/ha",
            transform=ax.transAxes, ha="right", va="bottom", fontsize=9, color=GREY)
    ax.legend(frameon=False, fontsize=10, loc="lower left")
    fig.subplots_adjust(left=0.24)
    return fig


# ── driver ───────────────────────────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, default=Path("events_emep.csv"))
    p.add_argument("--outdir", type=Path, default=Path("sensitivity_n2o"))
    p.add_argument("--scope", type=str, default="first rotation")
    p.add_argument("--ef-perturb", type=float, default=0.30)
    a = p.parse_args()
    a.outdir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(a.input)
    corr = df["NH3_emis_kgNha_EMEP"]
    base = df["NH3_emis_kgNha_base"]
    total_corr, total_base = corr.sum(), base.sum()
    subtitle = f"EMEP Tier 2 \u2014 {a.scope}  ·  {total_corr:.0f} kg NH$_3$-N/ha, {len(df)} events"

    # A. indirect N2O by system + total
    by_sys = df.groupby("Systeme")["NH3_emis_kgNha_EMEP"].sum()
    res = indirect_n2o(by_sys).reindex(_ordered(list(by_sys.index)))
    tot = indirect_n2o(pd.Series({"TOTAL": total_corr}))
    res.round(3).to_csv(a.outdir / "indirect_n2o_by_system.csv")
    fig_n2o_by_system(res, subtitle).savefig(
        a.outdir / "N2O_indirect_by_system.png", bbox_inches="tight"); plt.close()

    # B1. Entec structural toggle
    d_struct = total_corr - total_base
    co2_base = total_base * EF4 * N2O_PER_N2ON * GWP_DEFAULT
    co2_corr = total_corr * EF4 * N2O_PER_N2ON * GWP_DEFAULT

    # B2. EF OAT tornado
    tor = ef_tornado(df, a.ef_perturb)
    tor.round(3).to_csv(a.outdir / "sensitivity_ef_tornado.csv", index=False)
    fig_tornado(tor, total_corr, a.ef_perturb, subtitle).savefig(
        a.outdir / "sensitivity_ef_tornado.png", bbox_inches="tight"); plt.close()

    # B3 + B4. N2O parametric ranges
    n2o_mass = total_corr * EF4 * N2O_PER_N2ON
    summary = []
    summary.append(("NH3-N total, corrected (Entec ASN)", "kg N/ha", total_corr))
    summary.append(("NH3-N total, baseline (Entec AS)", "kg N/ha", total_base))
    summary.append(("Entec toggle effect on NH3-N", "kg N/ha", d_struct))
    summary.append(("N2O-N total", "kg N/ha", total_corr * EF4))
    summary.append(("N2O total", "kg/ha", n2o_mass))
    summary.append(("CO2eq central (EF4=0.010, GWP=273)", "kg CO2eq/ha", co2_corr))
    summary.append(("CO2eq low (EF4=0.002)", "kg CO2eq/ha",
                    total_corr * EF4_LOW * N2O_PER_N2ON * GWP_DEFAULT))
    summary.append(("CO2eq high (EF4=0.018)", "kg CO2eq/ha",
                    total_corr * EF4_HIGH * N2O_PER_N2ON * GWP_DEFAULT))
    summary.append(("Entec toggle effect on CO2eq", "kg CO2eq/ha", co2_corr - co2_base))
    for name, g in GWP.items():
        summary.append((f"CO2eq with GWP {name}", "kg CO2eq/ha", n2o_mass * g))
    sdf = pd.DataFrame(summary, columns=["quantity", "unit", "value"]).round(2)
    sdf.to_csv(a.outdir / "sensitivity_summary.csv", index=False)

    # console
    print(f"\n=== {a.scope} — {len(df)} events ===")
    print(f"NH3-N total: {total_corr:.1f} kg/ha (baseline {total_base:.1f}, "
          f"Entec effect {d_struct:+.1f})")
    print(f"Indirect N2O: {n2o_mass:.1f} kg N2O/ha  ->  "
          f"{co2_corr:.0f} kg CO2-eq/ha (range "
          f"{total_corr*EF4_LOW*N2O_PER_N2ON*GWP_DEFAULT:.0f}-"
          f"{total_corr*EF4_HIGH*N2O_PER_N2ON*GWP_DEFAULT:.0f})")
    print("\nMost influential NH3 emission factor (OAT tornado):")
    for r in tor.itertuples():
        print(f"  {r.category:20s}: +/-{a.ef_perturb:.0%} -> {r.delta_plus:+.0f} kg")
    print(f"\nWrote 3 CSVs + 2 figures to {a.outdir}")


if __name__ == "__main__":
    main()
