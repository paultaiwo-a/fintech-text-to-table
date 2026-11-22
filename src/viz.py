"""Chart style: color-blind safe, dense, editorial."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt

from src.paths import FIGURES_DIR

# Tableau Color Blind 10 (kept for accessibility)
TABLEAU_COLORBLIND = [
    "#1170aa",
    "#fc7d0b",
    "#a3acb9",
    "#57606c",
    "#5fa2ce",
    "#c85200",
    "#7b848f",
    "#a3cce9",
    "#ffbc79",
    "#c8d0d9",
]

INK = "#1c2430"
MUTED = "#6b7280"
GRID = "#e8ecf0"
TRACK = "#edf1f5"
ACCENT = "#1170aa"
HIGHLIGHT = "#fc7d0b"
SOFT = "#5fa2ce"

BLUE = ACCENT
ORANGE = HIGHLIGHT

PAIN_POINT_LABELS = {
    "fees": "Fees",
    "account_frozen_closed": "Account frozen / closed",
    "transfer_slow_failed": "Transfer slow / failed",
    "fraud_unauthorized": "Fraud / unauthorized",
    "service_unreachable": "Service unreachable",
    "funds_held_missing": "Funds held / missing",
    "digital_access": "Digital access",
    "promo_not_honored": "Promo not honored",
    "none": "No pain point",
}


def label_pain(code: str) -> str:
    return PAIN_POINT_LABELS.get(str(code), str(code).replace("_", " ").title())


def apply_style() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.edgecolor": GRID,
            "axes.labelcolor": INK,
            "xtick.color": MUTED,
            "ytick.color": INK,
            "text.color": INK,
            "axes.grid": False,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.spines.left": False,
            "axes.spines.bottom": True,
            "font.size": 11,
            "axes.titlesize": 14,
            "axes.titleweight": "semibold",
            "axes.labelsize": 11,
            "figure.dpi": 120,
        }
    )


def categorical_colors(n: int) -> list[str]:
    if n <= 0:
        return []
    return [TABLEAU_COLORBLIND[i % len(TABLEAU_COLORBLIND)] for i in range(n)]


def polish_axes(ax: plt.Axes, *, grid: str = "x") -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(axis="y", length=0)
    ax.tick_params(axis="x", colors=MUTED, length=3)
    if grid == "x":
        ax.xaxis.grid(True, color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
    elif grid == "y":
        ax.yaxis.grid(True, color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)


def save_fig(fig: plt.Figure, name: str, dpi: int = 160) -> Path:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    path = FIGURES_DIR / name
    fig.savefig(path, dpi=dpi, bbox_inches="tight", facecolor="white", pad_inches=0.25)
    return path
