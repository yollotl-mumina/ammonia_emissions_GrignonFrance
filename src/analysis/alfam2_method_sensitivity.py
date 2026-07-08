#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
alfam2_method_sensitivity.py
============================

Third sensitivity axis of the NH3 inventory: the ALFAM2 application-method
dependence, for the liquid organic events (cattle slurry + liquid digestate).

Two sub-analyses, both anchored on ALFAM2's own by-event outputs
(ALFAM2_*_alfam2_by_event.csv):

  1. MODEL-CHOICE sensitivity  (EMEP fixed 0.55*TAN  vs  ALFAM2 method-resolved)
     - per-event and totals over the liquid organic subset;
     - the indirect-N2O (IPCC EF4) implied by each model;
     - the effect on the WHOLE inventory when ALFAM2 replaces EMEP for these
       events (hybrid = full EMEP total - EMEP_liquid + ALFAM2_liquid).

  2. APPLICATION-METHOD counterfactual  (mitigation lever)
     - broadcast digestate events re-priced at the band-applied intensity that
       ALFAM2 gives for band digestate;
     - avoided NH3-N and avoided indirect N2O.
     NOTE: this is a DATA-DRIVEN estimate (band intensity borrowed from ALFAM2's
     band-digestate events, which occurred in cooler weather). A rigorous
     counterfactual re-runs the ALFAM2 R model with app.mthd = "bsth" and the
     real event weather; treat the avoided amount as an optimistic bracket.

Constants match 9_estimate_indirect_n2o.py (EF4, 44/28, GWP100 = 273).

Run
---
    python alfam2_method_sensitivity.py
      --input <path>/ALFAM2_entrada_horaria_alfam2_by_event.csv
      --outdir <path>/alfam2_sensitivity
      --full-emep-total 1125.5           # whole-inventory EMEP NH3-N (validated)
      --scope "full set (2018-2025)"
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

EF4, EF4_LOW, EF4_HIGH = 0.010, 0.002, 0.018
N2O_PER_N2ON = 44.0 / 28.0
GWP = 273.0
EF_ORGANIC = 0.55            # EMEP Tier 2 fixed factor for slurry / liquid digestate

plt.rcParams.update({
    "font.size": 12, "axes.titlesize": 15, "axes.titleweight": "bold",
    "figure.dpi": 160, "savefig.dpi": 160,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": "#E6E6E6", "grid.linewidth": 0.8,
})
GREY, EMEP_C, ALF_C, RED, GREEN = "#9AA0A6", "#9AA0A6", "#2F5597", "#C0392B", "#1F9E89"
METHOD_LABEL = {"bc": "Broadcast", "bsth": "Trailing hose (band)"}


def co2eq(nh3n, ef4=EF4):
    return nh3n * ef4 * N2O_PER_N2ON * GWP


def _titles(ax, title, subtitle):
    ax.set_title(title, pad=30)
    ax.text(0.0, 1.02, subtitle, transform=ax.transAxes, fontsize=10,
            color=GREY, va="bottom")


# ── figures ──────────────────────────────────────────────────────────────────
def fig_model_choice(g, subtitle):
    """EMEP vs ALFAM2 liquid-organic NH3-N, grouped by method x product."""
    g = g.copy()
    g["key"] = g["method_label"] + "\n" + g["Categorie_en"]
    x = np.arange(len(g)); w = 0.38
    fig, ax = plt.subplots(figsize=(9.5, 5.2))
    ax.grid(axis="y"); ax.set_axisbelow(True)
    ax.bar(x - w / 2, g["EMEP_kgNha"], width=w, color=EMEP_C,
           label="EMEP Tier 2 (0.55·TAN)", zorder=3)
    ax.bar(x + w / 2, g["ALFAM2_kgNha"], width=w, color=ALF_C,
           label="ALFAM2 (method-resolved)", zorder=3)
    top = float(g[["EMEP_kgNha", "ALFAM2_kgNha"]].values.max())
    for xi, r in zip(x, g.itertuples()):
        ax.text(xi - w / 2, r.EMEP_kgNha + top * 0.02, f"{r.EMEP_kgNha:.0f}",
                ha="center", va="bottom", fontsize=9, color="#555")
        ax.text(xi + w / 2, r.ALFAM2_kgNha + top * 0.02, f"{r.ALFAM2_kgNha:.0f}",
                ha="center", va="bottom", fontsize=9, color=ALF_C)
    ax.set_ylim(0, top * 1.15)
    ax.set_xticks(x); ax.set_xticklabels(g["key"])
    ax.set_ylabel("NH$_3$-N (kg N/ha)")
    _titles(ax, "Model-choice sensitivity: EMEP vs ALFAM2 (liquid organic)", subtitle)
    ax.legend(frameon=True, framealpha=0.9, edgecolor="none", fontsize=10,
              loc="upper center")
    return fig


def fig_mitigation(bc_mod, bc_band, avoided, av_co2, subtitle):
    """Broadcast digestate as modelled vs band-applied counterfactual."""
    fig, ax = plt.subplots(figsize=(7.5, 5.2))
    ax.grid(axis="y"); ax.set_axisbelow(True)
    cats = ["Broadcast\n(as modelled)", "Band-applied\n(counterfactual)"]
    vals = [bc_mod, bc_band]
    bars = ax.bar(cats, vals, color=[RED, GREEN], width=0.55, zorder=3)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + max(vals) * 0.02, f"{v:.0f}",
                ha="center", va="bottom", fontsize=11)
    ax.annotate(f"avoided\n{avoided:.0f} kg NH$_3$-N\n(\u2248 {av_co2:.0f} kg CO$_2$-eq)",
                xy=(1, bc_band), xytext=(0.5, (bc_mod + bc_band) / 2),
                ha="center", va="center", fontsize=10, color=RED, fontweight="bold",
                arrowprops=dict(arrowstyle="->", color=RED, lw=1.6))
    ax.set_ylim(0, bc_mod * 1.18)
    ax.set_ylabel("NH$_3$-N from broadcast digestate events (kg N/ha)")
    _titles(ax, "Mitigation lever: band application of digestate", subtitle)
    return fig


# ── driver ───────────────────────────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path,
                   default=Path("ALFAM2_entrada_horaria_alfam2_by_event.csv"))
    p.add_argument("--outdir", type=Path, default=Path("alfam2_sensitivity"))
    p.add_argument("--full-emep-total", type=float, default=1125.5,
                   help="whole-inventory EMEP NH3-N (kg/ha) for the hybrid context")
    p.add_argument("--scope", type=str, default="full set (2018-2025)")
    a = p.parse_args()
    a.outdir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(a.input)
    df["EMEP_kgNha"] = df["TAN_app_kgNha"] * EF_ORGANIC
    df.rename(columns={"NH3N_kgNha": "ALFAM2_kgNha"}, inplace=True)
    df["method_label"] = df["app_mthd"].map(METHOD_LABEL).fillna(df["app_mthd"])
    df["Categorie_en"] = df["Categorie"].map(
        {"Lisier": "Slurry", "Digestat liquide": "Digestate"}).fillna(df["Categorie"])
    n = len(df)
    subtitle = f"ALFAM2 vs EMEP Tier 2 \u2014 {a.scope}  ·  {n} liquid organic events"

    # --- 1. model choice ---
    g = (df.groupby(["method_label", "Categorie_en"], as_index=False)
           .agg(EMEP_kgNha=("EMEP_kgNha", "sum"),
                ALFAM2_kgNha=("ALFAM2_kgNha", "sum"),
                n=("ALFAM2_kgNha", "size")))
    g = g.sort_values(["Categorie_en", "method_label"])
    emep_liq, alf_liq = df["EMEP_kgNha"].sum(), df["ALFAM2_kgNha"].sum()
    df[["ID_evenement", "Systeme", "Categorie_en", "app_mthd", "TAN_app_kgNha",
        "EMEP_kgNha", "ALFAM2_kgNha", "emis_pct_TAN"]].round(3).to_csv(
        a.outdir / "alfam2_model_choice_by_event.csv", index=False)
    fig_model_choice(g, subtitle).savefig(
        a.outdir / "A6_model_choice_by_method.png", bbox_inches="tight"); plt.close()

    hybrid_total = a.full_emep_total - emep_liq + alf_liq

    # --- 2. band counterfactual for broadcast digestate ---
    band_int = (df[(df.app_mthd == "bsth") & (df.Categorie_en == "Digestate")]
                ["emis_pct_TAN"].mean() / 100.0)
    bc_dig = df[(df.app_mthd == "bc") & (df.Categorie_en == "Digestate")].copy()
    bc_dig["band_cf_kgNha"] = bc_dig["TAN_app_kgNha"] * band_int
    bc_dig["avoided_kgNha"] = bc_dig["ALFAM2_kgNha"] - bc_dig["band_cf_kgNha"]
    bc_mod = bc_dig["ALFAM2_kgNha"].sum()
    bc_band = bc_dig["band_cf_kgNha"].sum()
    avoided = bc_mod - bc_band
    av_co2 = co2eq(avoided)
    bc_dig[["ID_evenement", "Systeme", "TAN_app_kgNha", "ALFAM2_kgNha",
            "band_cf_kgNha", "avoided_kgNha"]].round(3).to_csv(
        a.outdir / "mitigation_band_counterfactual.csv", index=False)
    fig_mitigation(bc_mod, bc_band, avoided, av_co2, subtitle).savefig(
        a.outdir / "A7_band_mitigation.png", bbox_inches="tight"); plt.close()

    # --- summary ---
    S = []
    S.append(("Liquid-organic NH3-N, EMEP (0.55*TAN)", "kg N/ha", emep_liq))
    S.append(("Liquid-organic NH3-N, ALFAM2", "kg N/ha", alf_liq))
    S.append(("Model-choice effect (ALFAM2 - EMEP), liquid organic", "kg N/ha", alf_liq - emep_liq))
    S.append(("ALFAM2/EMEP ratio (sum, liquid organic)", "-", alf_liq / emep_liq))
    S.append(("Liquid-organic indirect N2O, EMEP", "kg CO2eq/ha", co2eq(emep_liq)))
    S.append(("Liquid-organic indirect N2O, ALFAM2", "kg CO2eq/ha", co2eq(alf_liq)))
    S.append(("Model-choice effect on indirect N2O", "kg CO2eq/ha", co2eq(alf_liq) - co2eq(emep_liq)))
    S.append(("Whole inventory, EMEP only", "kg N/ha", a.full_emep_total))
    S.append(("Whole inventory, hybrid (ALFAM2 for liquid organic)", "kg N/ha", hybrid_total))
    S.append(("Whole-inventory shift from model choice", "kg N/ha", hybrid_total - a.full_emep_total))
    S.append(("Band intensity used (ALFAM2 band digestate)", "% TAN", band_int * 100))
    S.append(("Broadcast digestate NH3-N, as modelled", "kg N/ha", bc_mod))
    S.append(("Broadcast digestate NH3-N, band counterfactual", "kg N/ha", bc_band))
    S.append(("Avoided NH3-N by band application", "kg N/ha", avoided))
    S.append(("Avoided indirect N2O (central EF4)", "kg CO2eq/ha", av_co2))
    S.append(("Avoided indirect N2O (EF4 low-high)", "kg CO2eq/ha range",
              f"{co2eq(avoided, EF4_LOW):.0f}-{co2eq(avoided, EF4_HIGH):.0f}"))
    sdf = pd.DataFrame(S, columns=["quantity", "unit", "value"])
    sdf["value"] = sdf["value"].map(lambda v: round(v, 2) if isinstance(v, (int, float)) else v)
    sdf.to_csv(a.outdir / "alfam2_method_sensitivity_summary.csv", index=False)

    print(f"\n=== ALFAM2 method sensitivity — {a.scope} ({n} events) ===")
    print(f"Liquid organic NH3-N: EMEP {emep_liq:.1f} vs ALFAM2 {alf_liq:.1f} kg "
          f"(ratio {alf_liq/emep_liq:.2f}); indirect N2O {co2eq(emep_liq):.0f} -> {co2eq(alf_liq):.0f} CO2eq")
    print(f"Whole inventory: {a.full_emep_total:.0f} -> hybrid {hybrid_total:.0f} kg NH3-N "
          f"({(hybrid_total-a.full_emep_total)/a.full_emep_total*100:+.1f}%)")
    print(f"Band mitigation (broadcast digestate): {bc_mod:.0f} -> {bc_band:.0f} kg "
          f"(band {band_int*100:.0f}% TAN); avoided {avoided:.0f} kg NH3-N "
          f"= {av_co2:.0f} kg CO2eq (range {co2eq(avoided,EF4_LOW):.0f}-{co2eq(avoided,EF4_HIGH):.0f})")
    print(f"Wrote 3 CSVs + 2 figures to {a.outdir}")


if __name__ == "__main__":
    main()
