"""Run analysis SQL and write simple charts (matplotlib + light plotly)."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from config.viz import BLUE, ORANGE, apply_style, categorical_colors, save_fig
from src.paths import ANALYSIS_SQL_DIR, DB_PATH, FIGURES_DIR
from src.pipeline.ingest import init_db


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
    if df.empty:
        print("No rows for switching-by-pain-point (try lowering HAVING threshold)")
        return None

    apply_style()
    plot_df = df.sort_values("switching_rate")
    colors = categorical_colors(len(plot_df))

    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.barh(plot_df["pain_point_code"], plot_df["switching_rate"], color=colors)
    ax.set_xlabel("Switching rate")
    ax.set_ylabel("Pain point")
    ax.set_title("Switching rate by pain point")
    path = save_fig(fig, "switching_by_pain_point.png")
    plt.close(fig)
    return path


def chart_lead_signal_hist(df: pd.DataFrame) -> Path | None:
    if df.empty:
        return None
    apply_style()
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(df["lead_signal_score"], bins=20, color=BLUE, edgecolor="white")
    ax.set_xlabel("Lead signal score")
    ax.set_ylabel("Interactions")
    ax.set_title("Lead signal score distribution")
    path = save_fig(fig, "lead_signal_distribution.png")
    plt.close(fig)
    return path


def chart_monthly_trend(df: pd.DataFrame, top_n: int = 4) -> Path | None:
    if df.empty:
        return None

    # focus on the most common pain points for a readable line chart
    top = (
        df.groupby("primary_pain_point")["interactions"]
        .sum()
        .sort_values(ascending=False)
        .head(top_n)
        .index
    )
    plot_df = df.loc[df["primary_pain_point"].isin(top)].copy()
    if plot_df.empty:
        return None

    apply_style()
    fig, ax = plt.subplots(figsize=(8, 4.5))
    colors = categorical_colors(len(top))
    for color, code in zip(colors, top):
        part = plot_df.loc[plot_df["primary_pain_point"] == code].sort_values("month")
        ax.plot(part["month"], part["switching_rate"], marker="o", color=color, label=code)
    ax.set_xlabel("Month")
    ax.set_ylabel("Switching rate")
    ax.set_title("Monthly switching rate (top pain points)")
    ax.tick_params(axis="x", rotation=45)
    ax.legend(frameon=False, fontsize=9)
    path = save_fig(fig, "monthly_switching_trend.png")
    plt.close(fig)
    return path


def chart_severity_vs_switching(db_path: Path = DB_PATH) -> Path | None:
    con = init_db(db_path)
    try:
        df = pd.read_sql(
            """
            SELECT primary_pain_point,
                   AVG(severity_score) AS avg_severity,
                   AVG(switching_intent) AS switching_rate,
                   COUNT(*) AS n
            FROM fct_interaction
            WHERE needs_review = 0 AND primary_pain_point != 'none'
            GROUP BY primary_pain_point
            HAVING COUNT(*) >= 100
            """,
            con,
        )
    finally:
        con.close()

    if df.empty:
        return None

    apply_style()
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.scatter(
        df["avg_severity"],
        df["switching_rate"],
        s=df["n"] / df["n"].max() * 400,
        c=ORANGE,
        alpha=0.85,
        edgecolors="#57606c",
    )
    for _, row in df.iterrows():
        ax.annotate(row["primary_pain_point"], (row["avg_severity"], row["switching_rate"]), fontsize=8)
    ax.set_xlabel("Avg severity score")
    ax.set_ylabel("Switching rate")
    ax.set_title("Severity vs switching by pain point")
    path = save_fig(fig, "severity_vs_switching.png")
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
    fig = go.Figure(
        data=[
            go.Table(
                header=dict(
                    values=list(show.columns),
                    fill_color=BLUE,
                    font=dict(color="white", size=12),
                    align="left",
                ),
                cells=dict(
                    values=[show[c] for c in show.columns],
                    fill_color="#f7f8fa",
                    align="left",
                ),
            )
        ]
    )
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
            f"Highest switching rate: {top['pain_point_code']} "
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
    paths = {
        "switching_chart": chart_switching_by_pain_point(tables["switching"]),
        "lead_hist": chart_lead_signal_hist(tables["lead_hist"]),
        "monthly_trend": chart_monthly_trend(tables["monthly"]),
        "severity_scatter": chart_severity_vs_switching(db_path),
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
