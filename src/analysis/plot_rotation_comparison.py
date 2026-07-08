#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R1 vs R2: why the absolute total is misleading. Three panels — absolute total,
per-year, and intensity (% of applied N) — computed from the two events_emep.csv."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

plt.rcParams.update({"font.size": 11, "axes.spines.top": False, "axes.spines.right": False,
                     "figure.dpi": 160, "savefig.dpi": 160})
GREY, BLUE = "#9AA0A6", "#2F5597"

def load(p):
    d = pd.read_csv(p); d["Date"] = pd.to_datetime(d["Date"])
    span = (d["Date"].max() - d["Date"].min()).days / 365.25
    nh3 = d["NH3_emis_kgNha_EMEP"].sum(); napp = d["N_applied_kgNha"].sum()
    return dict(total=nh3, per_year=nh3/span, intensity=100*nh3/napp,
               span=span, napp=napp, n=len(d))

r1 = load("results/emep/first_rotation/events_emep.csv")
r2 = load("results/emep/second_rotation/events_emep.csv")

panels = [
    ("Absolute total", "kg NH$_3$-N/ha", "total", "confounded by record length"),
    ("Per year", "kg NH$_3$-N/ha/yr", "per_year", "exposure removed"),
    ("Intensity", "% of applied N", "intensity", "exposure removed"),
]
fig, axes = plt.subplots(1, 3, figsize=(11, 4.4))
for ax, (title, ylab, key, tag) in zip(axes, panels):
    v1, v2 = r1[key], r2[key]
    ax.bar([0, 1], [v1, v2], color=[GREY, BLUE], width=0.6, zorder=3)
    ax.grid(axis="y", color="#E6E6E6"); ax.set_axisbelow(True)
    for x, v in zip([0, 1], [v1, v2]):
        ax.text(x, v + max(v1, v2)*0.02, f"{v:.1f}", ha="center", va="bottom", fontsize=10)
    delta = (v2 - v1) / v1 * 100
    col = "#C0392B" if delta < 0 else "#1F9E89"
    ax.text(0.5, max(v1, v2)*1.13, f"{delta:+.0f}%", ha="center", va="bottom",
            fontsize=13, fontweight="bold", color=col, transform=ax.transData)
    ax.set_ylim(0, max(v1, v2)*1.28)
    ax.set_xticks([0, 1]); ax.set_xticklabels(["R1", "R2"])
    ax.set_title(title, fontsize=13, fontweight="bold", pad=18)
    ax.set_ylabel(ylab)
    ax.text(0.5, 0.94, tag, transform=ax.transAxes, ha="center", va="top",
            fontsize=8.5, color="#888", style="italic")

fig.suptitle("Comparing the two rotations: the absolute drop is a record-length effect",
             fontsize=15, fontweight="bold", y=1.02)
fig.text(0.5, 0.965,
         f"R1: {r1['n']} events, {r1['span']:.1f} yr, {r1['napp']:.0f} kg N/ha applied   \u2022   "
         f"R2: {r2['n']} events, {r2['span']:.1f} yr, {r2['napp']:.0f} kg N/ha applied",
         ha="center", fontsize=9.5, color="#666")
fig.tight_layout(rect=[0, 0, 1, 0.94])
fig.savefig("figures/9_rotation_comparison_normalized.png", bbox_inches="tight")
print("R1", {k: round(v,1) for k,v in r1.items()})
print("R2", {k: round(v,1) for k,v in r2.items()})
print("saved")
