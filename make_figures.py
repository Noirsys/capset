#!/usr/bin/env python3
"""make_figures.py — single source of truth for every number in the merged paper.

Emits:
  figures/fig1_three_forms.pdf     the pipeline's three instances, instrumental vs reflexive
  figures/fig2_channel_closure.pdf the shadow-channel result (12/12 -> 0/12) and channel disposition
  figures/fig3_frontier.pdf        cap-set lower/upper frontier with this work marked
  tables/numbers.tex               \newcommand macros — prose never hand-types a number
  metrics.json                     machine-checkable copy (paper root)
All numbers are read from the two subjects' own records; nothing here is invented.
"""
import json
import pathlib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

ROOT = pathlib.Path(__file__).resolve().parent
FIG = ROOT / "figures"
TAB = ROOT / "tables"
FIG.mkdir(exist_ok=True)
TAB.mkdir(exist_ok=True)

# Okabe-Ito, colourblind-safe
OI = {
    "orange": "#E69F00", "sky": "#56B4E9", "green": "#009E73",
    "yellow": "#F0E442", "blue": "#0072B2", "red": "#D55E00",
    "purple": "#CC79A7", "grey": "#4D4D4D", "black": "#000000",
}
plt.rcParams.update({
    "font.family": "serif", "font.size": 8, "axes.linewidth": 0.6,
    "pdf.fonttype": 42, "axes.edgecolor": "#333333",
})

# ----------------------------------------------------------------------------
# Data. Provenance in comments; every value traceable to a file on disk.
# ----------------------------------------------------------------------------
# NoirStar: research-papers/noirstar/metrics.json
NS = {
    "shadow_n": 12, "shadow_old_pass": 12, "shadow_new_pass": 0,
    "attacks_total": 9, "attacks_defeated_filter": 6,
    "trajectories_scanned": 140, "trajectories_used": 0,
    "shadow_reproduced": 8, "shadow_attempts": 8,
    "ticks": 361, "runs": 146, "hypotheses": 53, "negatives": 23,
    "graduations": 0, "commits": 1951, "spend_usd": 2.171,
    "lesion_haiku_L0": 0.7963, "lesion_haiku_L1": 0.6852,
    "lesion_haiku_L2": 0.8333, "lesion_qwen_L0": 0.9815,
    "pass_visible": 0.8667, "pass_sealed": 0.9000, "pass_adversarial": 0.9250,
}
# Cap sets: capset_project/v2 records + RECORDS-FRONTIER-2026-10-22.md
CAPS = {
    # n: (lower bound, who, upper bound or None)
    "n":    [6,     7,     8,     9,     10,    11,     12],
    "lower": [112,  236,   512,   1084,  2432,  5529,   12928],
    "upper": [112,  291,   771,   2070,  5619,  16857,  None],
    "prior": [112,  236,   512,   1082,  2432,  5504,   12928],
    "new":   [False, False, False, True,  False, True,   False],
}

# ----------------------------------------------------------------------------
# Figure 1 — the three instances.  Geometry exposed as a table (see doctrine:
# text overflow is measured, not eyeballed; all labels kept short on purpose).
# ----------------------------------------------------------------------------
BOXES = []  # (x, y, w, h, title, line2, colour)
def _f1():
    fig, ax = plt.subplots(figsize=(7.1, 2.55), layout="constrained")
    ax.set_xlim(0, 14.2); ax.set_ylim(0, 5.1); ax.axis("off")
    boxes = [
        (0.25, 2.55, 3.9, 1.95, "I. Software", "instrumental", OI["sky"]),
        (5.15, 2.55, 3.9, 1.95, "II. Business", "instrumental", OI["green"]),
        (10.05, 2.55, 3.9, 1.95, "III. Research", "reflexive", OI["orange"]),
    ]
    BOXES.clear()
    for (x, y, w, h, t1, t2, c) in boxes:
        BOXES.append((x, y, w, h, t1, t2))
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.10",
                                    linewidth=1.1, edgecolor=c,
                                    facecolor=c, alpha=0.18))
        ax.text(x + w / 2, y + h - 0.62, t1, ha="center", va="center",
                fontsize=9.5, fontweight="bold")
        ax.text(x + w / 2, y + 0.60, t2, ha="center", va="center",
                fontsize=8.5, style="italic", color="#333333")
    # what each produces
    outs = [(2.2, "produces software"), (7.1, "produces customers"),
            (12.0, "produces\nevidence about itself")]
    for (xc, s) in outs:
        ax.text(xc, 1.62, s, ha="center", va="center", fontsize=7.8,
                color="#333333")
    # arrows along the lineage
    for x0, x1 in ((4.28, 5.05), (9.18, 9.95)):
        ax.add_patch(FancyArrowPatch((x0, 3.52), (x1, 3.52),
                                     arrowstyle="-|>,head_width=3,head_length=5",
                                     linewidth=1.1, color="#444444"))
    # the loop turning back on itself
    ax.add_patch(FancyArrowPatch((12.0, 2.45), (12.0, 0.42),
                                 connectionstyle="arc3,rad=0.55",
                                 arrowstyle="-|>,head_width=3,head_length=5",
                                 linewidth=1.1, color=OI["orange"], linestyle="--"))
    ax.annotate("subject of the third instance\nis the first two",
                xy=(13.35, 1.05), xytext=(9.35, 0.62), fontsize=7.4,
                color=OI["orange"], ha="left", va="center")
    ax.text(0.25, 4.86, "Same engine: constitution, ledger, external verifier",
            fontsize=8.2, fontweight="bold", ha="left", va="center")
    fig.savefig(FIG / "fig1_three_forms.pdf", bbox_inches="tight")
    plt.close(fig)

# ----------------------------------------------------------------------------
# Figure 2 — the shadow channel, and how the nine channels ended up.
# ----------------------------------------------------------------------------
def _f2():
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.1, 2.85),
                                 layout="constrained",
                                 gridspec_kw={"width_ratios": [1.0, 1.35]})
    # left: 12/12 -> 0/12
    labels = ["before fix", "after fix"]
    vals = [NS["shadow_old_pass"], NS["shadow_new_pass"]]
    cols = [OI["red"], OI["blue"]]
    bars = a1.bar(labels, vals, color=cols, width=0.55, edgecolor="#222222",
                  linewidth=0.6)
    for b, v in zip(bars, vals):
        a1.text(b.get_x() + b.get_width() / 2, v + 0.35, str(v),
                ha="center", va="bottom", fontsize=10, fontweight="bold")
    a1.set_ylim(0, 14.5)
    a1.set_ylabel("unsolved items reported as passed")
    a1.set_title(f"in-tree module shadowing (n = {NS['shadow_n']})",
                 fontsize=8.5)
    a1.axhline(NS["shadow_n"], color="#999999", linewidth=0.6, linestyle=":")
    a1.text(1.42, NS["shadow_n"] + 0.25, "all", fontsize=7, color="#777777",
            ha="right")

    # right: capability vs propensity — the honest pairing
    cats = ["defeated\nthe filter", "used it in\nproduction"]
    vals2 = [NS["attacks_defeated_filter"], NS["trajectories_used"]]
    cols2 = [OI["orange"], OI["blue"]]
    bars2 = a2.bar(cats, vals2, color=cols2, width=0.55, edgecolor="#222222",
                   linewidth=0.6)
    for b, v in zip(bars2, vals2):
        a2.text(b.get_x() + b.get_width() / 2, v + 0.55, str(v),
                ha="center", va="bottom", fontsize=10, fontweight="bold")
    a2.set_ylim(0, 9.5)
    a2.set_ylabel("count")
    a2.set_title(f"of {NS['attacks_total']} constructions, "
                 f"{NS['trajectories_scanned']} trajectories", fontsize=8.5)
    a2.text(0, -0.30, f"{NS['attacks_defeated_filter']} of "
             f"{NS['attacks_total']}", ha="center", va="top",
             transform=a2.get_xaxis_transform(), fontsize=7, color="#555555")
    a2.text(1, -0.30, f"0 of {NS['trajectories_scanned']}",
             transform=a2.get_xaxis_transform(), fontsize=7,
             color="#555555")
    fig.savefig(FIG / "fig2_channel_closure.pdf", bbox_inches="tight")
    plt.close(fig)

# ----------------------------------------------------------------------------
# Figure 3 — the cap-set frontier. Lower bounds rise; the gap is the point.
# ----------------------------------------------------------------------------
def _f3():
    fig, ax = plt.subplots(figsize=(7.1, 3.15), layout="constrained")
    n = CAPS["n"]
    up = [(x, y) for x, y in zip(n, CAPS["upper"]) if y is not None]
    ax.plot([p[0] for p in up], [p[1] for p in up], marker="s", ms=4.5,
            color=OI["grey"], linewidth=1.2, label="upper bound (known)")
    ax.plot(n, CAPS["lower"], marker="o", ms=5.0, color=OI["blue"],
            linewidth=1.4, label="lower bound (construction)")
    ax.plot(n, CAPS["prior"], marker="x", ms=4.5, color=OI["orange"],
            linewidth=0, label="prior lower bound")
    for x, y, isn in zip(n, CAPS["lower"], CAPS["new"]):
        if isn:
            ax.annotate(f"{y}\nwas {CAPS['prior'][n.index(x)]}",
                        xy=(x, y), xytext=(x - 0.55, y * 1.9),
                        fontsize=7.2, color=OI["red"], ha="center",
                        arrowprops=dict(arrowstyle="-", color=OI["red"],
                                        linewidth=0.7))
    ax.set_yscale("log")
    ax.set_xticks(n)
    ax.set_xlabel("dimension $n$ (caps in $\\mathbb{F}_3^n$)")
    ax.set_ylabel("cap size (log scale)")
    ax.grid(True, which="major", linewidth=0.35, color="#DDDDDD")
    ax.legend(fontsize=7.4, loc="upper left", frameon=False)
    ax.set_xlim(5.6, 12.5)
    fig.savefig(FIG / "fig3_frontier.pdf", bbox_inches="tight")
    plt.close(fig)

# ----------------------------------------------------------------------------
# Macros
# ----------------------------------------------------------------------------
def _macros():
    m = {
        "ShadowN": f"{NS['shadow_n']}",
        "ShadowOldPass": f"{NS['shadow_old_pass']}",
        "ShadowNewPass": f"{NS['shadow_new_pass']}",
        "AttacksTotal": f"{NS['attacks_total']}",
        "AttacksDefeated": f"{NS['attacks_defeated_filter']}",
        "TrajectoriesScanned": f"{NS['trajectories_scanned']}",
        "TrajectoriesUsed": f"{NS['trajectories_used']}",
        "ShadowReproduced": f"{NS['shadow_reproduced']}",
        "ShadowAttempts": f"{NS['shadow_attempts']}",
        "Ticks": f"{NS['ticks']}",
        "Runs": f"{NS['runs']}",
        "Hypotheses": f"{NS['hypotheses']}",
        "Negatives": f"{NS['negatives']}",
        "Graduations": f"{NS['graduations']}",
        "Commits": f"{NS['commits']:,}".replace(",", "{,}"),
        "Spend": f"{NS['spend_usd']:.2f}",
        "LesionHaikuA": f"{NS['lesion_haiku_L0']*100:.1f}",
        "LesionHaikuB": f"{NS['lesion_haiku_L1']*100:.1f}",
        "LesionHaikuC": f"{NS['lesion_haiku_L2']*100:.1f}",
        "LesionQwen": f"{NS['lesion_qwen_L0']*100:.1f}",
        "PassVisible": f"{NS['pass_visible']*100:.1f}",
        "PassSealed": f"{NS['pass_sealed']*100:.1f}",
        "PassAdversarial": f"{NS['pass_adversarial']*100:.1f}",
        "CapNine": f"{CAPS['lower'][3]}",
        "CapNinePrior": f"{CAPS['prior'][3]}",
        "CapEleven": f"{CAPS['lower'][5]}",
        "CapElevenPrior": f"{CAPS['prior'][5]}",
        "CapNineDelta": f"{CAPS['lower'][3]-CAPS['prior'][3]}",
        "CapElevenDelta": f"{CAPS['lower'][5]-CAPS['prior'][5]}",
        "CapNineUpper": f"{CAPS['upper'][3]}",
        "CapElevenUpper": f"{CAPS['upper'][5]}",
    }
    for k in m:                      # doctrine: names must be alphabetic only
        assert k.isalpha(), f"non-alphabetic macro name: {k}"
    lines = ["% generated by make_figures.py - do not edit", ""]
    for k, v in m.items():
        lines.append(f"\\newcommand{{\\Num{k}}}{{{v}}}")
    (TAB / "numbers.tex").write_text("\n".join(lines) + "\n")
    return m

def main():
    _f1(); _f2(); _f3()
    mac = _macros()
    payload = {"noirstar": NS, "caps": CAPS,
               "macros": mac, "source": "noirstar/metrics.json + capset records"}
    out = json.dumps(payload, indent=2, sort_keys=True)
    (ROOT / "metrics.json").write_text(out + "\n")
    (TAB / "metrics.json").write_text(out + "\n")
    print(out)
    for f in sorted(FIG.glob("*.pdf")):
        print("figure:", f.name, f.stat().st_size, "bytes")
    print("macros:", len(mac))
    print("boxes:", BOXES)

if __name__ == "__main__":
    main()
