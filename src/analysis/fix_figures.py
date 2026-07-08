#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Regenerate report figures 4, 5, 6 and 8 with clean, non-overlapping layout.
Explanatory text goes in titles/subtitles or dedicated margins, never floating
over the data; legends sit outside the axes or as direct line labels; generous
headroom everywhere."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

plt.rcParams.update({"font.size": 12, "axes.spines.top": False, "axes.spines.right": False,
                     "figure.dpi": 160, "savefig.dpi": 160})
GREY, BLUE, ORANGE, RED, GREEN = "#9AA0A6", "#2F5597", "#C55A11", "#C0392B", "#1F9E89"
IMG = "figures/"

# ============================================================ FIG 4 — A6 abated
b = pd.read_csv("results/alfam2/ALFAM2_entrada_horaria_alfam2_by_event.csv")
b["EMEP_ab"] = np.where(b.app_mthd == "bsth", b.TAN_app_kgNha*0.55*0.70, b.TAN_app_kgNha*0.55)
b["Prod"] = b.Categorie.map({"Lisier": "Slurry", "Digestat liquide": "Digestate"})
b["Meth"] = b.app_mthd.map({"bc": "Broadcast", "bsth": "Band"})
g = b.groupby(["Meth", "Prod"], as_index=False).agg(EMEP_ab=("EMEP_ab", "sum"),
                                                     ALFAM2=("NH3N_kgNha", "sum"))
order = ["Broadcast\nDigestate", "Band\nDigestate", "Broadcast\nSlurry", "Band\nSlurry"]
g["key"] = g.Meth + "\n" + g.Prod
g = g.set_index("key").reindex(order).reset_index()
ratio_ab = b.NH3N_kgNha.sum() / b.EMEP_ab.sum()
ratio_raw = b.NH3N_kgNha.sum() / (b.TAN_app_kgNha*0.55).sum()

fig, ax = plt.subplots(figsize=(9.2, 5.6))
x = np.arange(len(g)); w = 0.38
ax.grid(axis="y", color="#E6E6E6"); ax.set_axisbelow(True)
ax.bar(x - w/2, g.EMEP_ab, w, color=GREY, label="EMEP Tier 2 (band events abated \u221230%)")
ax.bar(x + w/2, g.ALFAM2, w, color=BLUE, label="ALFAM2 (method-resolved)")
top = float(g[["EMEP_ab", "ALFAM2"]].values.max())
for xi, r in zip(x, g.itertuples()):
    ax.text(xi - w/2, r.EMEP_ab + top*0.02, f"{r.EMEP_ab:.0f}", ha="center", va="bottom", fontsize=9, color="#555")
    ax.text(xi + w/2, r.ALFAM2 + top*0.02, f"{r.ALFAM2:.0f}", ha="center", va="bottom", fontsize=9, color=BLUE)
ax.set_ylim(0, top*1.15)
ax.set_xticks(x); ax.set_xticklabels(g.key)
ax.set_ylabel("NH$_3$-N (kg N/ha)")
ax.legend(frameon=False, fontsize=10, loc="upper center",
          bbox_to_anchor=(0.5, -0.14), ncol=2)
fig.suptitle("Model comparison with EMEP band abatement: EMEP vs ALFAM2",
             fontsize=14, fontweight="bold", y=0.99)
fig.text(0.5, 0.925, "Liquid organic events (full set). Totals agree once EMEP is abated: "
         f"ratio ALFAM2/EMEP = {ratio_ab:.2f} ({ratio_raw:.2f} unabated); distribution still differs by method.",
         ha="center", va="top", fontsize=9.3, color="#666")
fig.subplots_adjust(bottom=0.24, top=0.83)
fig.savefig(IMG + "4_EMEP_vs_ALFAM2_by_method.png", bbox_inches="tight")
plt.close()

# ============================================================ FIG 5 — A2 curves
H = pd.read_csv("results/alfam2/ALFAM2_entrada_horaria_alfam2_hourly.csv")
fig, ax = plt.subplots(figsize=(9.2, 5.4))
ax.grid(True, color="#EDEDED"); ax.set_axisbelow(True)
for eid, gg in H.groupby("ID_evenement"):
    gg = gg.sort_values("ct"); m = gg["app.mthd"].iloc[0]
    ax.plot(gg.ct, gg.er*100, color=(ORANGE if m == "bc" else BLUE), lw=1.8, alpha=0.85)
xmax = H.ct.max()
# direct labels instead of a legend (no overlap with curves)
ax.text(xmax*0.62, 86, "Broadcast (bc)", color=ORANGE, fontsize=11, fontweight="bold", va="center")
ax.text(xmax*0.62, 50, "Trailing hose / band (bsth)", color=BLUE, fontsize=11, fontweight="bold", va="center")
ax.annotate("", xy=(xmax*0.98, 43), xytext=(xmax*0.78, 49),
            arrowprops=dict(arrowstyle="-", color=BLUE, lw=0.8, alpha=0.6))
ax.set_xlim(0, xmax*1.02); ax.set_ylim(0, 95)
ax.set_xlabel("Hours since application (ct)")
ax.set_ylabel("Cumulative emission (% of applied TAN)")
ax.set_title("ALFAM2 cumulative emission as % of TAN", fontsize=14, fontweight="bold", pad=26)
ax.text(0.0, 1.02, "Full set (11 liquid organic events). Broadcast reaches ~80% within hours; "
        "band spreading emits less and more slowly.", transform=ax.transAxes,
        fontsize=9.3, color="#666", va="bottom")
fig.subplots_adjust(top=0.86)
fig.savefig(IMG + "5_ALFAM2_cumulative_pctTAN_over_time.png", bbox_inches="tight")
plt.close()

# ============================================================ FIG 6 — A7 mitig.
cf = pd.read_csv("results/alfam2_rerun/alfam2_counterfactual_R.csv")
bc_mod = 52.248*len(cf); bc_band = cf.NH3N_kgNha.sum()
band_pct = cf.pct_TAN.mean(); avoided = bc_mod - bc_band
av_co2 = avoided*0.010*(44/28)*273
fig, ax = plt.subplots(figsize=(7.8, 5.8))
ax.grid(axis="y", color="#E6E6E6"); ax.set_axisbelow(True)
bars = ax.bar([0, 1], [bc_mod, bc_band], color=[RED, GREEN], width=0.52)
for xi, v, pct in zip([0, 1], [bc_mod, bc_band], [83, band_pct]):
    ax.text(xi, v + bc_mod*0.02, f"{v:.0f} kg", ha="center", va="bottom", fontsize=12, fontweight="bold")
    ax.text(xi, v*0.5, f"{pct:.0f}%\nof TAN", ha="center", va="center", fontsize=11, color="white", fontweight="bold")
ax.set_ylim(0, bc_mod*1.16); ax.set_xlim(-0.55, 1.55)
ax.set_xticks([0, 1]); ax.set_xticklabels(["Broadcast\n(as modelled)", "Band\n(real re-run)"], fontsize=12)
ax.set_ylabel("NH$_3$-N from the 2 broadcast digestate events (kg N/ha)")
ax.set_title("Mitigation lever: band application of digestate", fontsize=14, fontweight="bold", pad=30)
ax.text(0.5, 1.045, f"Real ALFAM2 re-run under actual July weather (app.mthd = bsth): "
        f"band application avoids \u2248{avoided:.0f} kg NH$_3$-N/ha (\u2248{av_co2:.0f} kg CO$_2$-eq).",
        transform=ax.transAxes, ha="center", va="bottom", fontsize=9.3, color="#666")
fig.subplots_adjust(top=0.85)
fig.savefig(IMG + "6_band_application_mitigation.png", bbox_inches="tight")
plt.close()

# ============================================================ FIG 8 — rotations
def load(p):
    d = pd.read_csv(p); d.Date = pd.to_datetime(d.Date)
    span = (d.Date.max() - d.Date.min()).days/365.25
    nh3 = d.NH3_emis_kgNha_EMEP.sum(); napp = d.N_applied_kgNha.sum()
    return dict(total=nh3, per_year=nh3/span, intensity=100*nh3/napp, span=span, napp=napp, n=len(d))
r1 = load("results/emep/first_rotation/events_emep.csv")
r2 = load("results/emep/second_rotation/events_emep.csv")
panels = [("Absolute total", "kg NH$_3$-N/ha", "total", "confounded by record length"),
          ("Per year", "kg NH$_3$-N/ha/yr", "per_year", "exposure removed"),
          ("Intensity", "% of applied N", "intensity", "exposure removed")]
fig, axes = plt.subplots(1, 3, figsize=(11, 4.9))
for ax, (title, ylab, key, tag) in zip(axes, panels):
    v1, v2 = r1[key], r2[key]
    ax.bar([0, 1], [v1, v2], color=[GREY, BLUE], width=0.6)
    ax.grid(axis="y", color="#E6E6E6"); ax.set_axisbelow(True)
    for xx, v in zip([0, 1], [v1, v2]):
        ax.text(xx, v + max(v1, v2)*0.02, f"{v:.1f}", ha="center", va="bottom", fontsize=10)
    delta = (v2 - v1)/v1*100
    col = RED if delta < 0 else GREEN
    ax.text(0.5, max(v1, v2)*1.16, f"{delta:+.0f}%", ha="center", va="bottom",
            fontsize=14, fontweight="bold", color=col)
    ax.set_ylim(0, max(v1, v2)*1.34)
    ax.set_xticks([0, 1]); ax.set_xticklabels(["R1", "R2"])
    ax.set_title(title, fontsize=13, fontweight="bold", pad=10)
    ax.set_ylabel(ylab)
    ax.set_xlabel(tag, fontsize=9, style="italic", color="#888", labelpad=8)
fig.suptitle("Comparing the two rotations: the absolute drop is a record-length effect",
             fontsize=15, fontweight="bold", y=1.07)
fig.text(0.5, 0.99,
         f"R1: {r1['n']} events, {r1['span']:.1f} yr, {r1['napp']:.0f} kg N/ha applied      "
         f"R2: {r2['n']} events, {r2['span']:.1f} yr, {r2['napp']:.0f} kg N/ha applied",
         ha="center", fontsize=9.5, color="#666")
fig.tight_layout(rect=[0, 0, 1, 0.92])
fig.savefig(IMG + "9_rotation_comparison_normalized.png", bbox_inches="tight")
plt.close()

print("regenerated figures 4, 5, 6, 8")
for f in ["4_EMEP_vs_ALFAM2_by_method", "5_ALFAM2_cumulative_pctTAN_over_time",
          "6_band_application_mitigation", "9_rotation_comparison_normalized"]:
    from PIL import Image
    im = Image.open(IMG + f + ".png"); print(f, im.size, "h@600w=", round(600*im.size[1]/im.size[0]))
