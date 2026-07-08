#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Clarity-fixed ALFAM2 figures (A1-A5) + mitigation figure from the real
R re-run. Reads the ALFAM2 hourly + by_event CSVs and the R counterfactual.

Clarity fixes vs the originals:
  * event labels are 'date . product . system' (no cryptic '4u/5u');
  * a note flags that same-date COM/CTR and LOM/MF rows are the SAME digestate
    applied to two real systems (not duplicates);
  * method legend spelled out (bc = broadcast, bsth = trailing hose / band);
  * A7 uses the REAL ALFAM2 band re-run (not the same-intensity estimate).
"""
from __future__ import annotations
import argparse
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

plt.rcParams.update({
    "font.size": 12, "axes.titlesize": 15, "axes.titleweight": "bold",
    "figure.dpi": 160, "savefig.dpi": 160,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": "#E6E6E6", "grid.linewidth": 0.8,
})
ORANGE, BLUE, GREY, RED, GREEN, TEAL = \
    "#C55A11", "#2F5597", "#9AA0A6", "#C0392B", "#1F9E89", "#4FB0AE"
M_COLOR = {"bc": ORANGE, "bsth": BLUE}
M_NAME = {"bc": "Broadcast (bc)", "bsth": "Trailing hose / band (bsth)"}
P_NAME = {"Lisier": "Slurry", "Digestat liquide": "Digestate"}
P_COLOR = {"Slurry": GREEN, "Digestate": TEAL}
SUB = "ALFAM2 (Set 3, alfam2pars03) \u2014 full set (2018-2025), 11 liquid organic events"


def _titles(ax, t, s=SUB):
    ax.set_title(t, pad=30)
    ax.text(0.0, 1.02, s, transform=ax.transAxes, fontsize=9.5, color=GREY, va="bottom")


def ev_label(r):
    return f"{r['Date']} · {P_NAME.get(r['Categorie'], r['Categorie'])} · {r['Systeme']}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hourly", default="results/alfam2/ALFAM2_entrada_horaria_alfam2_hourly.csv")
    ap.add_argument("--byevent", default="results/alfam2/ALFAM2_entrada_horaria_alfam2_by_event.csv")
    ap.add_argument("--cf", default="results/alfam2_rerun/alfam2_counterfactual_R.csv")
    ap.add_argument("--outdir", default="alfam2_figs_clear")
    a = ap.parse_args()
    out = Path(a.outdir); out.mkdir(parents=True, exist_ok=True)

    H = pd.read_csv(a.hourly)
    B = pd.read_csv(a.byevent)
    B["label"] = B.apply(ev_label, axis=1)
    NOTE = ("Same-date rows on two systems (e.g. CTR/COM & MF/LOM digestate) are the "
            "SAME product applied to two real systems, not duplicates.")

    # ── A1: cumulative kg over time ─────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(9, 5.2))
    ax.grid(True); ax.set_axisbelow(True)
    for eid, g in H.groupby("ID_evenement"):
        g = g.sort_values("ct"); m = g["app.mthd"].iloc[0]
        ax.plot(g["ct"], g["e"], color=M_COLOR.get(m, GREY), lw=1.8, alpha=0.9)
    for m, nm in M_NAME.items():
        ax.plot([], [], color=M_COLOR[m], lw=2, label=nm)
    ax.set_xlabel("Hours since application (ct)")
    ax.set_ylabel("Cumulative NH$_3$-N emission (kg N/ha)")
    _titles(ax, "ALFAM2 cumulative NH$_3$-N emission over time")
    ax.annotate("broadcast digestate\n(hot July event)", xy=(60, 52), xytext=(60, 40),
                fontsize=9, color=ORANGE, ha="center",
                arrowprops=dict(arrowstyle="->", color=ORANGE))
    ax.legend(frameon=False, fontsize=10, loc="center right")
    fig.savefig(out / "A1_cumulative_kg_over_time.png", bbox_inches="tight"); plt.close()

    # ── A2: cumulative % of TAN over time ───────────────────────────────────
    fig, ax = plt.subplots(figsize=(9, 5.2))
    ax.grid(True); ax.set_axisbelow(True)
    for eid, g in H.groupby("ID_evenement"):
        g = g.sort_values("ct"); m = g["app.mthd"].iloc[0]
        ax.plot(g["ct"], g["er"] * 100, color=M_COLOR.get(m, GREY), lw=1.8, alpha=0.9)
    for m, nm in M_NAME.items():
        ax.plot([], [], color=M_COLOR[m], lw=2, label=nm)
    ax.set_xlabel("Hours since application (ct)")
    ax.set_ylabel("Cumulative emission (% of applied TAN)")
    _titles(ax, "ALFAM2 cumulative emission as % of TAN")
    ax.legend(frameon=False, fontsize=10, loc="center right")
    fig.savefig(out / "A2_cumulative_pct_over_time.png", bbox_inches="tight"); plt.close()

    # ── A3: final emission by event (clear labels) ──────────────────────────
    b = B.sort_values("NH3N_kgNha")
    fig, ax = plt.subplots(figsize=(10, 5.6))
    ax.grid(axis="x"); ax.set_axisbelow(True)
    colors = [M_COLOR.get(m, GREY) for m in b["app_mthd"]]
    ax.barh(b["label"], b["NH3N_kgNha"], color=colors, zorder=3)
    for y, v in enumerate(b["NH3N_kgNha"]):
        ax.text(v + b["NH3N_kgNha"].max() * 0.01, y, f" {v:.1f}", va="center", fontsize=9)
    ax.set_xlim(0, b["NH3N_kgNha"].max() * 1.12)
    ax.set_xlabel("Final cumulative NH$_3$-N emission (kg N/ha)")
    _titles(ax, "ALFAM2 final NH$_3$-N emission by event")
    for m, nm in M_NAME.items():
        ax.barh([], [], color=M_COLOR[m], label=nm)
    ax.legend(frameon=False, fontsize=10, loc="lower right")
    ax.text(0.0, -0.17, NOTE, transform=ax.transAxes, fontsize=8.5, color=GREY)
    fig.savefig(out / "A3_emission_by_event.png", bbox_inches="tight"); plt.close()

    # ── A4: intensity by method x product with event points ─────────────────
    B["Prod"] = B["Categorie"].map(P_NAME)
    grp = (B.groupby(["app_mthd", "Prod"])
             .agg(mean=("emis_pct_TAN", "mean"), n=("emis_pct_TAN", "size")).reset_index())
    grp["key"] = grp["app_mthd"].map({"bc": "Broadcast", "bsth": "Band"}) + "\n" + grp["Prod"]
    grp = grp.sort_values("mean")
    fig, ax = plt.subplots(figsize=(9, 5.2))
    ax.grid(axis="y"); ax.set_axisbelow(True)
    x = np.arange(len(grp))
    ax.bar(x, grp["mean"], color=[P_COLOR[p] for p in grp["Prod"]], width=0.6, zorder=3)
    for xi, row in zip(x, grp.itertuples()):
        ax.text(xi, row.mean + 2, f"mean {row.mean:.0f}%\n(n={row.n})",
                ha="center", va="bottom", fontsize=9)
        sub = B[(B.app_mthd == row.app_mthd) & (B.Prod == row.Prod)]
        ax.scatter([xi] * len(sub), sub["emis_pct_TAN"], color="#333", s=22, zorder=4)
    ax.set_ylim(0, 100); ax.set_xticks(x); ax.set_xticklabels(grp["key"])
    ax.set_ylabel("Emission intensity (% of applied TAN)")
    _titles(ax, "ALFAM2 emission intensity by method and product")
    ax.scatter([], [], color="#333", s=22, label="individual events")
    ax.legend(frameon=False, fontsize=9, loc="upper left")
    fig.savefig(out / "A4_intensity_by_method.png", bbox_inches="tight"); plt.close()

    # ── A5: by system, stacked by product ───────────────────────────────────
    piv = (B.assign(Prod=B["Categorie"].map(P_NAME))
             .pivot_table(index="Systeme", columns="Prod", values="NH3N_kgNha",
                          aggfunc="sum", fill_value=0.0))
    fig, ax = plt.subplots(figsize=(7.5, 5.2))
    ax.grid(axis="y"); ax.set_axisbelow(True)
    bottom = np.zeros(len(piv))
    for prod in ["Digestate", "Slurry"]:
        if prod in piv:
            ax.bar(piv.index, piv[prod], bottom=bottom, color=P_COLOR[prod],
                   label=prod, zorder=3)
            bottom += piv[prod].values
    for xi, t in enumerate(bottom):
        ax.text(xi, t + bottom.max() * 0.015, f"{t:.1f}", ha="center", va="bottom", fontsize=10)
    ax.set_ylim(0, bottom.max() * 1.12)
    ax.set_ylabel("Cumulative NH$_3$-N emission (kg N/ha)")
    _titles(ax, "ALFAM2 NH$_3$-N by system, stacked by product")
    ax.legend(frameon=False, fontsize=10, title="Product", loc="upper left")
    ax.text(0.0, -0.14, NOTE, transform=ax.transAxes, fontsize=8.5, color=GREY)
    fig.savefig(out / "A5_emission_by_system.png", bbox_inches="tight"); plt.close()

    # ── A7: REAL band-application counterfactual (from R re-run) ─────────────
    cf = pd.read_csv(a.cf)
    bc_mod = 52.248 * len(cf)
    bc_band = cf["NH3N_kgNha"].sum()
    avoided = bc_mod - bc_band
    EF4, GWP, R = 0.010, 273, 44 / 28
    av_co2 = avoided * EF4 * R * GWP
    band_pct = cf["pct_TAN"].mean()
    fig, ax = plt.subplots(figsize=(7.8, 5.4))
    ax.grid(axis="y"); ax.set_axisbelow(True)
    bars = ax.bar(["Broadcast\n(as modelled)\n83% TAN",
                   f"Band, real re-run\n{band_pct:.0f}% TAN"],
                  [bc_mod, bc_band], color=[RED, GREEN], width=0.55, zorder=3)
    for b, v in zip(bars, [bc_mod, bc_band]):
        ax.text(b.get_x() + b.get_width() / 2, v + bc_mod * 0.02, f"{v:.0f}",
                ha="center", va="bottom", fontsize=11)
    ax.annotate(f"avoided {avoided:.0f} kg NH$_3$-N\n\u2248 {av_co2:.0f} kg CO$_2$-eq/ha",
                xy=(1, bc_band), xytext=(0.5, (bc_mod + bc_band) / 2 + 8),
                ha="center", va="center", fontsize=10, color=RED, fontweight="bold",
                arrowprops=dict(arrowstyle="->", color=RED, lw=1.6))
    ax.set_ylim(0, bc_mod * 1.2)
    ax.set_ylabel("NH$_3$-N from the 2 broadcast digestate events (kg N/ha)")
    _titles(ax, "Mitigation lever: band application (real ALFAM2 re-run)")
    ax.text(0.0, -0.17, "Both digestate events re-run with app.mthd = bsth under their real July weather. "
            "Naive same-intensity estimate (42.8%) gave 51 kg avoided; the real re-run gives far less "
            "because band still loses ~59% of TAN in the heat.", transform=ax.transAxes,
            fontsize=8.3, color=GREY, wrap=True)
    fig.savefig(out / "A7_band_mitigation_real.png", bbox_inches="tight"); plt.close()

    print("wrote A1-A5 + A7 to", out)
    print(f"Real counterfactual: broadcast {bc_mod:.0f} -> band {bc_band:.0f} kg "
          f"({band_pct:.0f}% TAN); avoided {avoided:.0f} kg NH3-N = {av_co2:.0f} kg CO2-eq")


if __name__ == "__main__":
    main()
