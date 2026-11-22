"""Run analysis SQL and write story-first charts."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

from src.paths import ANALYSIS_SQL_DIR, DB_PATH, FIGURES_DIR
from src.pipeline.ingest import init_db
from src.viz import (
    ACCENT,
    INK,
    MUTED,
    NEUTRAL,
    NEUTRAL_DARK,
    SOFT,
    add_header,
    apply_style,
    label_pain,
    polish_axes,
    save_fig,
    wilson_ci,
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
    """Dot + 95% Wilson interval per pain point, with an average line and a volume column.

    Replaces both the old lollipop and the volume-vs-switching bubble chart.
    Emphasis goes to the pain point with the highest *lower* interval bound,
    i.e. the strongest switching signal we can actually trust.
    """
    if df.empty:
        print("No rows for switching-by-pain-point (try lowering HAVING threshold)")
        return None

    apply_style()
    plot_df = df.sort_values("switching_rate").reset_index(drop=True).copy()
    plot_df["label"] = plot_df["pain_point_code"].map(label_pain)
    n_obs = plot_df["interactions"].to_numpy(dtype=float)
    rates = plot_df["switching_rate"].to_numpy(dtype=float)
    k = np.round(rates * n_obs)
    ci = np.array([wilson_ci(ki, ni) for ki, ni in zip(k, n_obs)])
    lo, hi = ci[:, 0], ci[:, 1]
    small = n_obs < 100
    avg = k.sum() / n_obs.sum()

    reliable = np.where(~small, lo, -1.0)
    best = int(np.argmax(reliable)) if (~small).any() else int(np.argmax(lo))
    best_name = plot_df.loc[best, "label"]

    n = len(plot_df)
    y = np.arange(n)
    fig_h = max(3.8, 0.5 * n + 2.4)
    fig, (ax, axv) = plt.subplots(
        1, 2, figsize=(9.4, fig_h), sharey=True,
        gridspec_kw={"width_ratios": [4, 1.05]},
    )

    colors = [ACCENT if i == best else NEUTRAL_DARK for i in range(n)]
    line_colors = [ACCENT if i == best else NEUTRAL for i in range(n)]

    ax.axvline(avg, color=NEUTRAL_DARK, linewidth=1, linestyle=(0, (4, 3)), zorder=1)
    ax.text(avg, n - 0.5, f" avg {avg:.1%}", ha="left", va="bottom",
            fontsize=9, color=MUTED)

    ax.hlines(y, lo, hi, colors=line_colors, linewidth=2.2, zorder=2)
    for i in range(n):
        face = "white" if small[i] else colors[i]
        ax.scatter(rates[i], y[i], s=95, facecolor=face, edgecolor=colors[i],
                   linewidths=2, zorder=3)
        label = f"{rates[i]:.1%}" + ("  (n<100)" if small[i] else "")
        ax.text(hi[i] + 0.004, y[i], label, va="center", ha="left",
                fontsize=10.5, color=INK, zorder=4,
                fontweight="semibold" if i == best else "regular",
                bbox=dict(facecolor="white", edgecolor="none", pad=1.5))

    ax.set_yticks(y)
    ax.set_yticklabels(plot_df["label"], fontsize=11)
    ax.set_xlim(0, hi.max() * 1.28)
    ax.set_ylim(-0.6, n - 0.15)
    ax.xaxis.set_major_formatter(mticker.PercentFormatter(1.0, decimals=0))
    ax.set_xlabel("Share of complaints mentioning switching (95% interval)")
    polish_axes(ax, grid="x")

    vol_colors = [ACCENT if i == best else NEUTRAL for i in range(n)]
    axv.barh(y, n_obs, height=0.32, color=vol_colors, zorder=2)
    for i in range(n):
        axv.text(n_obs[i] + n_obs.max() * 0.04, y[i], f"{int(n_obs[i]):,}",
                 va="center", ha="left", fontsize=9.5, color=MUTED)
    axv.set_xlim(0, n_obs.max() * 1.6)
    axv.text(0, n - 0.5, "Complaints", ha="left", va="bottom", fontsize=9, color=MUTED)
    axv.set_xticks([])
    axv.tick_params(axis="y", length=0)
    for spine in axv.spines.values():
        spine.set_visible(False)

    rect = add_header(
        fig,
        f"{best_name}: high switching, and a reliable estimate",
        "Switching rate with 95% interval  \u00b7  pain points with \u226550 complaints"
        "  \u00b7  hollow dot = fewer than 100 complaints",
    )
    # Fixed margins (tight_layout can't handle the shared-y volume column):
    # left leaves room for pain-point labels, bottom for the x label + source line.
    fig.subplots_adjust(left=0.23, right=0.98, wspace=0.05,
                        top=rect[3] - 0.03, bottom=rect[1] + 0.75 / fig_h)
    path = save_fig(fig, "switching_by_pain_point.png")
    plt.close(fig)
    return path


def chart_lead_funnel(df: pd.DataFrame) -> Path | None:
    """Lead-signal score bands on a linear scale, plus a zoom bar on the top bands.

    Replaces the old sqrt-width funnel, which exaggerated the hot slice.
    """
    if df.empty:
        return None

    apply_style()
    scores = df["lead_signal_score"].dropna().to_numpy(dtype=float)
    total = len(scores)
    if total == 0:
        return None
    bands = [
        ("0 to 24", int((scores < 25).sum()), "#c8d0d9"),
        ("25 to 49", int(((scores >= 25) & (scores < 50)).sum()), "#a3cce9"),
        ("Warm (50 to 74)", int(((scores >= 50) & (scores < 75)).sum()), SOFT),
        ("Hot (75+)", int((scores >= 75).sum()), ACCENT),
    ]
    warm, hot = bands[2][1], bands[3][1]
    top = warm + hot

    fig, ax = plt.subplots(figsize=(9.4, 3.9))
    bar_h = 0.30
    y_main, y_zoom = 1.0, 0.0

    left = 0.0
    lefts = []
    for name, count, color in bands:
        w = count / total
        lefts.append(left)
        ax.barh(y_main, w, left=left, height=bar_h, color=color,
                edgecolor="white", linewidth=1.5, zorder=2)
        left += w

    # Labels sit above the main bar so the zoom connectors never cross them.
    for (name, count, _), x0 in zip(bands[:2], lefts[:2]):
        ax.text(x0 + 0.004, y_main + bar_h / 2 + 0.05,
                f"{name}  \u00b7  {count:,} ({count / total:.0%})",
                ha="left", va="bottom", fontsize=9.5, color=INK)

    if top > 0:
        x_top = lefts[2]
        ax.barh(y_zoom, warm / top, left=0, height=bar_h, color=SOFT,
                edgecolor="white", linewidth=1.5, zorder=2)
        ax.barh(y_zoom, hot / top, left=warm / top, height=bar_h, color=ACCENT,
                edgecolor="white", linewidth=1.5, zorder=2)
        for x_from, x_to in ((x_top, 0.0), (1.0, 1.0)):
            ax.plot([x_from, x_to], [y_main - bar_h / 2, y_zoom + bar_h / 2],
                    color=NEUTRAL_DARK, linewidth=0.9, linestyle=(0, (3, 3)), zorder=1)
        ax.text(0.004, y_zoom - bar_h / 2 - 0.06, f"Warm (50 to 74)  \u00b7  {warm:,}",
                ha="left", va="top", fontsize=10, color=INK)
        ax.text(1.0, y_zoom - bar_h / 2 - 0.06, f"Hot (75+)  \u00b7  {hot:,}",
                ha="right", va="top", fontsize=11, color=INK, fontweight="semibold")

    ax.set_xlim(0, 1.0)
    ax.set_ylim(-0.5, 1.4)
    ax.axis("off")

    rect = add_header(
        fig,
        f"{hot:,} hot leads: {hot / total:.1%} of everything scored",
        f"Lead-signal score bands, linear scale  \u00b7  {total:,} interactions"
        f"  \u00b7  lower bar zooms into the top {top:,} ({top / total:.1%})",
    )
    fig.tight_layout(rect=rect)
    path = save_fig(fig, "lead_signal_distribution.png")
    plt.close(fig)
    return path


def chart_hot_leads_by_pain_point(df: pd.DataFrame, total_hot: int | None = None) -> Path | None:
    """Where hot leads concentrate: count and share of all hot leads."""
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
    total = int(total_hot) if total_hot else int(vals.sum())
    top_idx = int(np.argmax(vals))
    top_name = plot_df.iloc[top_idx]["label"]
    top_share = vals[top_idx] / total

    fig_h = max(3.0, 0.5 * n + 1.9)
    fig, ax = plt.subplots(figsize=(9.4, fig_h))
    colors = [ACCENT if i == top_idx else NEUTRAL for i in range(n)]
    ax.barh(y, vals, height=0.6, color=colors, zorder=2)

    for i, val in enumerate(vals):
        ax.text(val + vals.max() * 0.015, i, f"{int(val):,}  \u00b7  {val / total:.0%}",
                va="center", fontsize=10.5, color=INK,
                fontweight="semibold" if i == top_idx else "regular")

    ax.set_yticks(y)
    ax.set_yticklabels(plot_df["label"], fontsize=11)
    ax.set_xlim(0, vals.max() * 1.25)
    ax.set_ylim(-0.55, n - 0.45)
    ax.set_xticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(axis="y", length=0)

    other = total - int(vals.sum())
    subtitle = f"Hot leads (score \u226575) by primary pain point  \u00b7  {total:,} hot leads"
    if other > 0:
        subtitle += f"  \u00b7  {other:,} in smaller or unlabelled groups not shown"
    rect = add_header(
        fig,
        f"{top_share:.0%} of hot leads come from {top_name.lower()}",
        subtitle,
    )
    fig.tight_layout(rect=rect)
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
    for stale_name in (
        "severity_vs_switching.png",
        "monthly_switching_trend.png",
        "volume_vs_switching.png",
    ):
        stale = FIGURES_DIR / stale_name
        if stale.exists():
            stale.unlink()

    paths = {
        "switching_chart": chart_switching_by_pain_point(tables["switching"]),
        "lead_funnel": chart_lead_funnel(tables["lead_hist"]),
        "hot_leads": chart_hot_leads_by_pain_point(
            tables["switching"],
            total_hot=int((tables["lead_hist"]["lead_signal_score"] >= 75).sum()),
        ),
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
