"""Run analysis SQL and write story-first charts."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.paths import ANALYSIS_SQL_DIR, DB_PATH, FIGURES_DIR
from src.pipeline.ingest import init_db
from src.viz import (
    ACCENT,
    GRID,
    HIGHLIGHT,
    INK,
    MUTED,
    SOFT,
    TRACK,
    apply_style,
    label_pain,
    polish_axes,
    save_fig,
)


def _read_sql_file(name: str, con) -> pd.DataFrame:
    sql = (ANALYSIS_SQL_DIR / name).read_text()
    return pd.read_sql(sql, con)


def load_analysis_tables(db_path: Path = DB_PATH) -> dict[str, pd.DataFrame]:
    con = init_db(db_path)
    try:
        tables = {
            "switching": _read_sql_file("01_switching_by_pain_point.sql", con),
            "leads": _read_sql_file("02_top_lead_signals.sql", con),
            "monthly": _read_sql_file("03_monthly_trends.sql", con),
            "lead_hist": pd.read_sql(
                "SELECT lead_signal_score FROM fct_interaction WHERE needs_review = 0",
                con,
            ),
        }
    finally:
        con.close()
    return tables


def chart_switching_by_pain_point(df: pd.DataFrame) -> Path | None:
    """Ranked lollipop: which pain points carry the most switching language."""
    if df.empty:
        print("No rows for switching-by-pain-point (try lowering HAVING threshold)")
        return None

    apply_style()
    plot_df = df.sort_values("switching_rate").copy()
    plot_df["label"] = plot_df["pain_point_code"].map(label_pain)
    n = len(plot_df)
    y = np.arange(n)
    rates = plot_df["switching_rate"].to_numpy(dtype=float)
    top_idx = int(np.argmax(rates))
    top_name = plot_df.iloc[top_idx]["label"]

    fig_h = max(2.8, 0.48 * n + 1.35)
    fig, ax = plt.subplots(figsize=(9.4, fig_h))

    ax.hlines(y, 0, rates, color=TRACK, linewidth=8, zorder=1)
    colors = [HIGHLIGHT if i == top_idx else ACCENT for i in range(n)]
    ax.scatter(rates, y, s=130, c=colors, zorder=3, edgecolors="white", linewidths=1.8)

    for i, (rate, row) in enumerate(zip(rates, plot_df.itertuples())):
        ax.text(
            rate + max(rates) * 0.025,
            i,
            f"{rate:.1%}",
            va="center",
            ha="left",
            fontsize=11,
            color=INK,
            fontweight="semibold" if i == top_idx else "regular",
        )
        ax.text(
            rate + max(rates) * 0.025,
            i - 0.28,
            f"n={int(row.interactions):,}",
            va="top",
            ha="left",
            fontsize=8.5,
            color=MUTED,
        )

    ax.set_yticks(y)
    ax.set_yticklabels(plot_df["label"], fontsize=11)
    ax.set_xlim(0, max(rates) * 1.22)
    ax.set_ylim(-0.55, n - 0.45)
    ax.set_xlabel("Share mentioning switching")
    ax.set_title(f"{top_name} shows the highest switching rate", loc="left", pad=14)
    ax.text(
        0,
        1.02,
        "Pain points with ≥50 complaints  ·  Jan–Apr 2026",
        transform=ax.transAxes,
        fontsize=9.5,
        color=MUTED,
        va="bottom",
    )
    polish_axes(ax, grid="x")
    fig.tight_layout()
    path = save_fig(fig, "switching_by_pain_point.png")
    plt.close(fig)
    return path


def chart_volume_vs_switching(df: pd.DataFrame) -> Path | None:
    """Bubble chart: volume (x) vs switching (y) — high volume ≠ high switch."""
    if df.empty:
        return None

    apply_style()
    plot_df = df.copy()
    plot_df["label"] = plot_df["pain_point_code"].map(label_pain)
    x = plot_df["interactions"].to_numpy(dtype=float)
    y = plot_df["switching_rate"].to_numpy(dtype=float)
    sizes = np.sqrt(x) * 8
    sizes = np.clip(sizes, 80, 900)

    fig, ax = plt.subplots(figsize=(9.4, 5.6))
    ax.scatter(
        x,
        y,
        s=sizes,
        c=SOFT,
        alpha=0.9,
        edgecolors=ACCENT,
        linewidths=1.4,
        zorder=3,
    )

    # Manual offsets so labels don't sit on bubbles
    offsets = {
        "fraud_unauthorized": (12, -14),
        "account_frozen_closed": (12, 10),
        "fees": (12, -12),
        "service_unreachable": (12, 10),
        "funds_held_missing": (12, 8),
    }
    for _, row in plot_df.iterrows():
        dx, dy = offsets.get(row["pain_point_code"], (10, 0))
        ax.annotate(
            row["label"],
            (row["interactions"], row["switching_rate"]),
            xytext=(dx, dy),
            textcoords="offset points",
            fontsize=10,
            color=INK,
            va="center",
        )

    codes = plot_df.set_index("pain_point_code")
    if "fraud_unauthorized" in codes.index:
        ax.text(
            0.98,
            0.05,
            "Fraud: most complaints, least switching",
            transform=ax.transAxes,
            ha="right",
            fontsize=9.5,
            color=HIGHLIGHT,
            fontweight="semibold",
        )

    ax.set_xscale("log")
    ax.set_xlim(max(40, x.min() * 0.7), x.max() * 2.2)
    y_pad = (y.max() - y.min()) * 0.12
    ax.set_ylim(max(0, y.min() - y_pad), y.max() + y_pad)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))
    ax.set_xlabel("Complaint volume (log scale)")
    ax.set_ylabel("Switching rate")
    ax.set_title("Volume and switching tell different stories", loc="left", pad=14)
    ax.text(
        0,
        1.02,
        "Bubble size ∝ volume  ·  ≥50 complaints",
        transform=ax.transAxes,
        fontsize=9.5,
        color=MUTED,
        va="bottom",
    )
    polish_axes(ax, grid="y")
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    fig.tight_layout()
    path = save_fig(fig, "volume_vs_switching.png")
    plt.close(fig)
    return path


def chart_lead_funnel(df: pd.DataFrame) -> Path | None:
    """Step funnel of lead quality — labels outside bars so nothing clips."""
    if df.empty:
        return None

    apply_style()
    scores = df["lead_signal_score"].dropna().to_numpy(dtype=float)
    total = len(scores)
    mentioned = int((scores >= 25).sum())
    warm = int((scores >= 50).sum())
    hot = int((scores >= 75).sum())

    stages = [
        ("All scored", total, TRACK),
        ("Mentioned (≥25)", mentioned, SOFT),
        ("Warm (≥50)", warm, ACCENT),
        ("Hot leads (≥75)", hot, HIGHLIGHT),
    ]

    fig, ax = plt.subplots(figsize=(9.4, 4.2))
    y = np.arange(len(stages))[::-1]
    counts = np.array([s[1] for s in stages], dtype=float)
    # sqrt scale keeps the hot stage visible without lying about rank order
    draw_w = np.sqrt(counts)
    draw_w = draw_w / draw_w.max()

    for i, ((name, count, color), yi, w) in enumerate(zip(stages, y, draw_w)):
        ax.barh(yi, w, left=0, height=0.68, color=color, zorder=2)
        pct = count / total if total else 0
        ax.text(
            w + 0.03,
            yi,
            f"{name}  ·  {count:,}  ({pct:.1%})",
            ha="left",
            va="center",
            fontsize=12 if i == len(stages) - 1 else 11,
            color=INK,
            fontweight="semibold" if i == len(stages) - 1 else "regular",
            zorder=3,
        )
        if i < len(stages) - 1:
            nxt = stages[i + 1][1]
            keep = nxt / count if count else 0
            mid_y = (yi + y[i + 1]) / 2
            ax.text(
                0.01,
                mid_y,
                f"↓ {keep:.0%} keep",
                ha="left",
                va="center",
                fontsize=9,
                color=MUTED,
            )

    ax.set_xlim(0, 1.55)
    ax.set_ylim(-0.55, len(stages) - 0.45)
    ax.set_yticks([])
    ax.set_xticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_title(f"{hot:,} hot leads — the acquisition-ready slice", loc="left", pad=14)
    ax.text(
        0,
        1.03,
        "Lead-signal score funnel  ·  bar width uses √scale so the hot slice stays visible",
        transform=ax.transAxes,
        fontsize=9.5,
        color=MUTED,
        va="bottom",
    )
    fig.tight_layout()
    path = save_fig(fig, "lead_signal_distribution.png")
    plt.close(fig)
    return path


def chart_hot_leads_by_pain_point(df: pd.DataFrame) -> Path | None:
    """Where hot leads concentrate — actionable follow-up chart."""
    if df.empty or "hot_leads" not in df.columns:
        return None

    apply_style()
    plot_df = df.loc[df["hot_leads"] > 0].sort_values("hot_leads").copy()
    if plot_df.empty:
        return None

    plot_df["label"] = plot_df["pain_point_code"].map(label_pain)
    n = len(plot_df)
    y = np.arange(n)
    vals = plot_df["hot_leads"].to_numpy(dtype=float)
    top_idx = int(np.argmax(vals))
    top_name = plot_df.iloc[top_idx]["label"]

    fig_h = max(2.8, 0.5 * n + 1.35)
    fig, ax = plt.subplots(figsize=(9.4, fig_h))
    colors = [HIGHLIGHT if i == top_idx else ACCENT for i in range(n)]
    ax.barh(y, vals, height=0.62, color=colors, zorder=2)

    for i, (val, row) in enumerate(zip(vals, plot_df.itertuples())):
        ax.text(
            val + max(vals) * 0.02,
            i,
            f"{int(val):,}",
            va="center",
            fontsize=11,
            color=INK,
            fontweight="semibold" if i == top_idx else "regular",
        )

    ax.set_yticks(y)
    ax.set_yticklabels(plot_df["label"], fontsize=11)
    ax.set_xlabel("Hot leads (score ≥ 75)")
    ax.set_xlim(0, max(vals) * 1.18)
    ax.set_ylim(-0.55, n - 0.45)
    ax.set_title(f"Most hot leads sit in {top_name.lower()}", loc="left", pad=14)
    ax.text(
        0,
        1.02,
        "Rows with lead_signal_score ≥ 75 by primary pain point",
        transform=ax.transAxes,
        fontsize=9.5,
        color=MUTED,
        va="bottom",
    )
    polish_axes(ax, grid="x")
    fig.tight_layout()
    path = save_fig(fig, "hot_leads_by_pain_point.png")
    plt.close(fig)
    return path


def plotly_top_leads(df: pd.DataFrame) -> Path | None:
    """One interactive table for the demo notebook."""
    if df.empty:
        return None
    try:
        import plotly.graph_objects as go
    except ImportError:
        print("plotly not installed — skipping interactive leads table")
        return None

    show = df.head(50).copy()
    if "primary_pain_point" in show.columns:
        show["primary_pain_point"] = show["primary_pain_point"].map(label_pain)

    fig = go.Figure(
        data=[
            go.Table(
                header=dict(
                    values=[c.replace("_", " ").title() for c in show.columns],
                    fill_color=ACCENT,
                    font=dict(color="white", size=12, family="Inter, Helvetica, sans-serif"),
                    align="left",
                    height=32,
                ),
                cells=dict(
                    values=[show[c] for c in show.columns],
                    fill_color=[["#ffffff", "#f4f7fa"] * (len(show) // 2 + 1)],
                    align="left",
                    font=dict(color=INK, size=11),
                    height=28,
                ),
            )
        ]
    )
    fig.update_layout(margin=dict(l=8, r=8, t=8, b=8), paper_bgcolor="white")
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    path = FIGURES_DIR / "top_lead_signals.html"
    fig.write_html(str(path), include_plotlyjs="cdn")
    return path


def print_summary(tables: dict[str, pd.DataFrame]) -> None:
    switching = tables["switching"]
    leads = tables["leads"]
    print("\n=== Insights summary ===")
    if not switching.empty:
        top = switching.iloc[0]
        print(
            f"Highest switching rate: {label_pain(top['pain_point_code'])} "
            f"({top['switching_rate']:.1%}, n={int(top['interactions']):,})"
        )
        print(switching.to_string(index=False))
    else:
        print("Switching-by-pain-point: no groups met the volume floor.")
    print(f"\nTop lead-signal rows (>=75): {len(leads):,}")
    if not leads.empty:
        print(leads.head(10).to_string(index=False))


def run_insights(db_path: Path = DB_PATH) -> dict:
    tables = load_analysis_tables(db_path)
    for stale_name in ("severity_vs_switching.png", "monthly_switching_trend.png"):
        stale = FIGURES_DIR / stale_name
        if stale.exists():
            stale.unlink()

    paths = {
        "switching_chart": chart_switching_by_pain_point(tables["switching"]),
        "volume_vs_switching": chart_volume_vs_switching(tables["switching"]),
        "lead_funnel": chart_lead_funnel(tables["lead_hist"]),
        "hot_leads": chart_hot_leads_by_pain_point(tables["switching"]),
        "leads_html": plotly_top_leads(tables["leads"]),
    }
    print_summary(tables)
    written = {k: str(v) for k, v in paths.items() if v is not None}
    print("\nWrote figures:")
    for name, path in written.items():
        print(f"  {name}: {path}")
    return {"tables": tables, "figures": written}


if __name__ == "__main__":
    run_insights()
