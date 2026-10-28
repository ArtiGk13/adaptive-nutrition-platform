"""Figure 4.1 - the two flows, with the Supervisor gate marked on both.

Requires matplotlib, which is not a runtime dependency of the application:

    pip install matplotlib

Writes into docs/figures/ next to this repository, as both PNG and PDF at 300 dpi.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "figures"
OUT.mkdir(parents=True, exist_ok=True)

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


FONT = {"family": "serif", "size": 9}
plt.rc("font", **FONT)

GATE_FACE = "#4A4A4A"
BOX_FACE = "#FFFFFF"
SIDE_FACE = "#EDEDED"

fig, ax = plt.subplots(figsize=(7.2, 4.4))
ax.set_xlim(0, 10)
ax.set_ylim(0, 6.2)
ax.axis("off")

W, H = 1.55, 0.62


def box(x, y, label, *, face=BOX_FACE, text_colour="black", dashed=False, width=W):
    ax.add_patch(
        FancyBboxPatch(
            (x - width / 2, y - H / 2),
            width,
            H,
            boxstyle="round,pad=0.04,rounding_size=0.08",
            linewidth=1.0,
            edgecolor="black",
            facecolor=face,
            linestyle="--" if dashed else "-",
            zorder=2,
        )
    )
    ax.text(x, y, label, ha="center", va="center", color=text_colour, zorder=3, fontsize=8.5)


def arrow(x1, y1, x2, y2, *, dashed=False, label=None, label_dx=0.0, label_dy=0.16):
    ax.add_patch(
        FancyArrowPatch(
            (x1, y1),
            (x2, y2),
            arrowstyle="-|>",
            mutation_scale=11,
            linewidth=0.9,
            color="black",
            linestyle="--" if dashed else "-",
            shrinkA=2,
            shrinkB=2,
            zorder=1,
        )
    )
    if label:
        ax.text(
            (x1 + x2) / 2 + label_dx,
            (y1 + y2) / 2 + label_dy,
            label,
            ha="center",
            va="center",
            fontsize=7.2,
            style="italic",
        )


# ---------------------------------------------------------------- onboarding
ax.text(0.15, 5.85, "Onboarding", fontsize=9.5, fontweight="bold", va="center")

xs = [1.2, 3.3, 5.4, 7.8]
y = 5.0
box(xs[0], y, "User profile\nand history")
box(xs[1], y, "Planner")
box(xs[2], y, "Supervisor", face=GATE_FACE, text_colour="white")
box(xs[3], y, "Plan stored", width=1.8)

for a, b in zip(xs, xs[1:]):
    arrow(a + W / 2, y, b - (1.8 if b == xs[3] else W) / 2, y)
ax.text((xs[2] + xs[3]) / 2, y + 0.46, "approved", ha="center", fontsize=7.2, style="italic")

box(xs[2], 3.85, "Referral", face=SIDE_FACE, width=1.3)
arrow(xs[2], y - H / 2, xs[2], 3.85 + H / 2, label="rejected", label_dx=0.72, label_dy=0.0)

ax.plot([0.1, 9.9], [3.15, 3.15], color="#BBBBBB", linewidth=0.8, linestyle=":")

# ------------------------------------------------------------ adaptation cycle
ax.text(0.15, 2.82, "Adaptation cycle, weekly", fontsize=9.5, fontweight="bold", va="center")

cx = [1.1, 2.95, 4.8, 6.65, 8.75]
cy = 2.0
box(cx[0], cy, "Logged\nmeals, weight", width=1.6)
box(cx[1], cy, "Assessment")
box(cx[2], cy, "Adaptation")
box(cx[3], cy, "Supervisor", face=GATE_FACE, text_colour="white")
box(cx[4], cy, "Plan revised", width=1.7)

widths = [1.6, W, W, W, 1.7]
for (a, wa), (b, wb) in zip(zip(cx, widths), zip(cx[1:], widths[1:])):
    arrow(a + wa / 2, cy, b - wb / 2, cy)
ax.text((cx[3] + cx[4]) / 2, cy + 0.46, "approved", ha="center", fontsize=7.2, style="italic")

box(cx[3], 0.85, "Referral", face=SIDE_FACE, width=1.3)
arrow(cx[3], cy - H / 2, cx[3], 0.85 + H / 2, label="flagged", label_dx=0.68, label_dy=0.0)

box(cx[2], 0.85, "Tutor", face=SIDE_FACE, dashed=True, width=1.3)
arrow(cx[2], cy - H / 2, cx[2], 0.85 + H / 2, dashed=True)
box(cx[1] - 0.45, 0.85, "Feedback text", face=SIDE_FACE, dashed=True, width=1.75)
arrow(cx[2] - 1.3 / 2, 0.85, cx[1] - 0.45 + 1.75 / 2, 0.85, dashed=True)

ax.text(
    4.95,
    0.12,
    "Dashed: language model output, off the critical path. The cycle completes without it.",
    ha="center",
    fontsize=7.2,
    style="italic",
    color="#444444",
)

fig.tight_layout(pad=0.4)
for suffix in ("png", "pdf"):
    fig.savefig(OUT / f"figure_4_1_architecture.{suffix}", dpi=300, bbox_inches="tight")
print("written:", OUT / "figure_4_1_architecture.png")
