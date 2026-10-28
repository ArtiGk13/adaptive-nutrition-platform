"""Figure 6.1 - suitability and goal progress by scenario and configuration.

Read straight from data/evaluation/results.csv so the figure cannot drift from the
reported numbers.

Requires matplotlib, which is not a runtime dependency of the application:

    pip install matplotlib

Writes into docs/figures/ next to this repository, as both PNG and PDF at 300 dpi.
"""

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "figures"
OUT.mkdir(parents=True, exist_ok=True)

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np


plt.rc("font", family="serif", size=9)

rows = list(csv.DictReader((ROOT / "data" / "evaluation" / "results.csv").open(encoding="utf-8")))

LABELS = {
    "weight_loss_consistent": "Weight loss,\nconsistent",
    "weight_loss_low_tolerance": "Weight loss,\nlow tolerance",
    "weight_loss_poor_logging": "Weight loss,\nsparse logging",
    "weight_loss_over_restricting": "Weight loss,\nover-restricting",
    "maintenance_stable": "Maintenance",
    "muscle_gain_steady": "Muscle gain",
    "muscle_gain_low_tolerance": "Muscle gain,\nlow tolerance",
    "weight_loss_safety_risk": "Weight loss,\nsafety case",
}
# Scenarios the Supervisor refused have no run to plot; zeros would read as poor
# performance rather than as a refusal.
REFUSED = {r["scenario"] for r in rows if r.get("refused_at_onboarding") == "True"}
ORDER = [s for s in LABELS if s not in REFUSED]
STRATEGIES = [
    ("adaptive", "Adaptive", "#333333"),
    ("non_adaptive", "Non-adaptive", "#8C8C8C"),
    ("fixed", "Fixed plan", "#DCDCDC"),
]


def value(scenario, strategy, field):
    return float(
        next(r[field] for r in rows if r["scenario"] == scenario and r["strategy"] == strategy)
    )


fig, axes = plt.subplots(1, 2, figsize=(7.4, 4.6), sharey=True)
y = np.arange(len(ORDER))
height = 0.26

for ax, (field, title) in zip(axes, [("suitability", "Suitability"), ("goal_progress", "Goal progress")]):
    for index, (key, label, colour) in enumerate(STRATEGIES):
        offset = (index - 1) * height
        values = [value(s, key, field) for s in ORDER]
        ax.barh(
            y - offset,
            values,
            height=height,
            color=colour,
            edgecolor="black",
            linewidth=0.6,
            label=label if ax is axes[0] else None,
            zorder=3,
        )
    ax.set_xlim(0, 1.05)
    ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.set_title(title, fontsize=10, pad=8)
    ax.grid(axis="x", linestyle=":", linewidth=0.6, color="#BBBBBB", zorder=0)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)

axes[0].set_yticks(y)
axes[0].set_yticklabels([LABELS[s] for s in ORDER], fontsize=8)
axes[0].invert_yaxis()

handles, labels = axes[0].get_legend_handles_labels()
fig.legend(
    handles,
    labels,
    loc="lower center",
    ncol=3,
    frameon=False,
    fontsize=8.5,
    bbox_to_anchor=(0.54, -0.015),
)

fig.tight_layout(rect=(0, 0.06, 1, 1))
for suffix in ("png", "pdf"):
    fig.savefig(OUT / f"figure_6_1_results.{suffix}", dpi=300, bbox_inches="tight")

print("written:", OUT / "figure_6_1_results.png")
print("\nvalues plotted (checked against results.csv):")
for scenario in ORDER:
    suit = [f"{value(scenario, k, 'suitability'):.3f}" for k, _, _ in STRATEGIES]
    prog = [f"{value(scenario, k, 'goal_progress'):.3f}" for k, _, _ in STRATEGIES]
    print(f"   {scenario:<30} suit {suit}  progress {prog}")
