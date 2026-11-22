"""Evaluate extractors against hand labels; update dim_rule precision."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.paths import DB_PATH, LABELS_PATH, LABELS_TEMPLATE_PATH, RESULTS_DIR
from src.pipeline.ingest import init_db

TEMPLATE_PATH = LABELS_TEMPLATE_PATH
REPORTS_DIR = RESULTS_DIR

LABEL_FIELDS = [
    "primary_pain_point",
    "switching_intent",
    "amount_usd_max",
    "delay_days_max",
    "sentiment_label",
]


def load_labels(path: Path = LABELS_PATH) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"Missing labels at {path}. Copy {TEMPLATE_PATH.name}, "
            "fill ~150 rows from fct_interaction, save as labels.csv"
        )
    df = pd.read_csv(path)
    required = ["interaction_id"] + LABEL_FIELDS
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"labels.csv missing columns: {missing}")
    # drop template example if left in
    df = df.loc[~df["interaction_id"].astype(str).str.endswith("0000000")].copy()
    if df.empty:
        raise ValueError("labels.csv has no real rows yet")
    return df


def _binary_pr(y_true: pd.Series, y_pred: pd.Series) -> dict:
    yt = y_true.astype(int)
    yp = y_pred.astype(int)
    tp = int(((yt == 1) & (yp == 1)).sum())
    fp = int(((yt == 0) & (yp == 1)).sum())
    fn = int(((yt == 1) & (yp == 0)).sum())
    precision = tp / (tp + fp) if (tp + fp) else np.nan
    recall = tp / (tp + fn) if (tp + fn) else np.nan
    return {"precision": precision, "recall": recall, "support": int(yt.sum())}


def _exact_pr(y_true: pd.Series, y_pred: pd.Series) -> dict:
    mask = y_true.notna()
    yt = y_true[mask]
    yp = y_pred[mask]
    if len(yt) == 0:
        return {"precision": np.nan, "recall": np.nan, "support": 0}
    # treat accuracy as precision=recall for multi-class exact match summary
    acc = float((yt.astype(str) == yp.astype(str)).mean())
    return {"precision": acc, "recall": acc, "support": int(len(yt))}


def _amount_pr(y_true: pd.Series, y_pred: pd.Series, tol: float = 0.05) -> dict:
    mask = y_true.notna()
    yt = y_true[mask].astype(float)
    yp = y_pred[mask]
    if len(yt) == 0:
        return {"precision": np.nan, "recall": np.nan, "support": 0}
    # relative tolerance, or both null-ish
    ok = []
    for t, p in zip(yt, yp):
        if pd.isna(p):
            ok.append(False)
        elif t == 0:
            ok.append(abs(p) < 1)
        else:
            ok.append(abs(p - t) / abs(t) <= tol)
    acc = float(np.mean(ok))
    return {"precision": acc, "recall": acc, "support": int(len(yt))}


def _delay_pr(y_true: pd.Series, y_pred: pd.Series) -> dict:
    mask = y_true.notna()
    yt = y_true[mask].astype(float)
    yp = y_pred[mask]
    if len(yt) == 0:
        return {"precision": np.nan, "recall": np.nan, "support": 0}
    ok = []
    for t, p in zip(yt, yp):
        if pd.isna(p):
            ok.append(False)
        else:
            ok.append(abs(float(p) - t) <= 1)
    acc = float(np.mean(ok))
    return {"precision": acc, "recall": acc, "support": int(len(yt))}


def evaluate_fields(labels: pd.DataFrame, preds: pd.DataFrame) -> pd.DataFrame:
    merged = labels.merge(preds, on="interaction_id", how="inner", suffixes=("_true", "_pred"))
    if merged.empty:
        raise ValueError("No overlap between labels and fct_interaction")

    rows = []
    sw = _binary_pr(merged["switching_intent_true"], merged["switching_intent_pred"])
    rows.append({"field": "switching_intent", **sw})

    rows.append(
        {
            "field": "primary_pain_point",
            **_exact_pr(merged["primary_pain_point_true"], merged["primary_pain_point_pred"]),
        }
    )
    rows.append(
        {
            "field": "sentiment_label",
            **_exact_pr(merged["sentiment_label_true"], merged["sentiment_label_pred"]),
        }
    )
    rows.append(
        {
            "field": "amount_usd_max",
            **_amount_pr(merged["amount_usd_max_true"], merged["amount_usd_max_pred"]),
        }
    )
    rows.append(
        {
            "field": "delay_days_max",
            **_delay_pr(merged["delay_days_max_true"], merged["delay_days_max_pred"]),
        }
    )
    return pd.DataFrame(rows), merged


def crosstab_vs_cfpb_issue(con, labels: pd.DataFrame | None = None) -> pd.DataFrame:
    q = """
    SELECT f.interaction_id, f.primary_pain_point, r.issue
    FROM fct_interaction f
    JOIN raw_complaints r
      ON f.source_record_id = r.complaint_id
    """
    df = pd.read_sql(q, con)
    if labels is not None:
        df = df.loc[df["interaction_id"].isin(labels["interaction_id"])]
    return pd.crosstab(df["issue"], df["primary_pain_point"])


def update_rule_precision(con, merged: pd.DataFrame) -> int:
    """
    Approximate per-rule precision for switching_intent rules:
    among labelled rows where the rule fired, share where switching_intent_true=1.
    """
    evidence = pd.read_sql(
        """
        SELECT interaction_id, rule_id
        FROM fct_extraction_evidence
        WHERE field_name = 'switching_intent'
        """,
        con,
    )
    if evidence.empty:
        return 0

    labelled = merged[["interaction_id", "switching_intent_true"]]
    hit = evidence.merge(labelled, on="interaction_id", how="inner")
    if hit.empty:
        return 0

    by_rule = (
        hit.groupby("rule_id")["switching_intent_true"]
        .agg(precision_on_labels="mean", n="size")
        .reset_index()
    )

    updated = 0
    for row in by_rule.itertuples(index=False):
        con.execute(
            """
            UPDATE dim_rule
            SET precision_on_labels = ?
            WHERE rule_id = ?
            """,
            (float(row.precision_on_labels), row.rule_id),
        )
        updated += 1
    con.commit()
    return updated


def run_evaluation(
    db_path: Path = DB_PATH,
    labels_path: Path = LABELS_PATH,
    min_switching_precision: float = 0.85,
) -> dict:
    labels = load_labels(labels_path)
    con = init_db(db_path)
    try:
        preds = pd.read_sql(
            f"""
            SELECT interaction_id, {", ".join(LABEL_FIELDS)}
            FROM fct_interaction
            """,
            con,
        )
        metrics, merged = evaluate_fields(labels, preds)
        xtab = crosstab_vs_cfpb_issue(con, labels)
        n_rules = update_rule_precision(con, merged)
    finally:
        con.close()

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    metrics_path = REPORTS_DIR / "evaluation_metrics.csv"
    xtab_path = REPORTS_DIR / "pain_point_vs_cfpb_issue.csv"
    metrics.to_csv(metrics_path, index=False)
    xtab.to_csv(xtab_path)

    sw = metrics.loc[metrics["field"] == "switching_intent", "precision"]
    sw_precision = float(sw.iloc[0]) if len(sw) else float("nan")

    print(metrics.to_string(index=False))
    print(f"\nUpdated precision_on_labels for {n_rules} switching rules")
    print(f"Wrote {metrics_path} and {xtab_path}")

    if sw_precision < min_switching_precision:
        print(
            f"WARNING: switching_intent precision {sw_precision:.3f} "
            f"< target {min_switching_precision:.2f} — tighten SW-* rules"
        )

    return {
        "metrics": metrics,
        "crosstab": xtab,
        "switching_precision": sw_precision,
        "n_labelled": len(merged),
        "rules_updated": n_rules,
    }


def sample_for_labelling(db_path: Path = DB_PATH, n: int = 150, seed: int = 42) -> Path:
    """Write a starter label file with IDs to annotate (predictions blanked)."""
    con = init_db(db_path)
    try:
        df = pd.read_sql(
            """
            SELECT interaction_id, primary_pain_point, switching_intent,
                   amount_usd_max, delay_days_max, sentiment_label
            FROM fct_interaction
            """,
            con,
        )
    finally:
        con.close()

    if len(df) < n:
        raise ValueError(f"Only {len(df)} interactions available; need {n}")

    sample = df.sample(n=n, random_state=seed).copy()
    # blank prediction columns so you fill ground truth, not copy model output
    sample["primary_pain_point"] = ""
    sample["switching_intent"] = ""
    sample["amount_usd_max"] = ""
    sample["delay_days_max"] = ""
    sample["sentiment_label"] = ""
    sample["notes"] = ""

    out = LABELS_PATH.parent / "labels_to_annotate.csv"
    sample.to_csv(out, index=False)
    print(f"Wrote {out} ({n} rows). Fill labels, save as labels.csv")
    return out


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "sample":
        sample_for_labelling()
    else:
        run_evaluation()
