"""Tableau Color Blind 10 palette and small matplotlib helpers."""

from pathlib import Path

import matplotlib.pyplot as plt

# Tableau Color Blind 10
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

BLUE = TABLEAU_COLORBLIND[0]
ORANGE = TABLEAU_COLORBLIND[1]
FIGURES_DIR = Path(__file__).resolve().parents[1] / "output" / "figures"


def apply_style() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.edgecolor": "#57606c",
            "axes.labelcolor": "#57606c",
            "xtick.color": "#57606c",
            "ytick.color": "#57606c",
            "text.color": "#57606c",
            "axes.grid": True,
            "grid.color": "#c8d0d9",
            "grid.linewidth": 0.6,
            "axes.axisbelow": True,
            "font.size": 11,
        }
    )


def categorical_colors(n: int) -> list[str]:
    if n <= 0:
        return []
    return [TABLEAU_COLORBLIND[i % len(TABLEAU_COLORBLIND)] for i in range(n)]


def save_fig(fig: plt.Figure, name: str, dpi: int = 120) -> Path:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    path = FIGURES_DIR / name
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    return path
