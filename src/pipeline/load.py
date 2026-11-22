"""Load scored interactions into SQLite fact tables."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.pipeline.extract import extract_all
from src.pipeline.ingest import DB_PATH, init_db
from src.pipeline.schema import column_names
from src.pipeline.score import apply_scores
from src.pipeline.seed import seed_dimensions

from src.paths import EXPORTS_DIR


def _nullify_nans(df: pd.DataFrame) -> pd.DataFrame:
    return df.where(pd.notnull(df), None)


def clear_facts(con) -> None:
    con.execute("DELETE FROM fct_extraction_evidence")
    con.execute("DELETE FROM fct_interaction_pain_point")
    con.execute("DELETE FROM fct_interaction")


def load_facts(
    interactions: pd.DataFrame,
    pain_points: pd.DataFrame,
    evidence: pd.DataFrame,
    db_path: Path = DB_PATH,
    seed: bool = True,
) -> dict:
    if interactions.empty:
        raise ValueError("No interactions to load")

    cols = column_names("fct_interaction")
    missing = [c for c in cols if c not in interactions.columns]
    if missing:
        raise ValueError(f"Missing columns for fct_interaction: {missing}")

    fact = _nullify_nans(interactions[cols].copy())

    if seed:
        seed_dimensions(db_path)

    con = init_db(db_path)
    try:
        con.execute("PRAGMA foreign_keys = ON")
        clear_facts(con)

        fact.to_sql("fct_interaction", con, if_exists="append", index=False)

        if not pain_points.empty:
            pp = _nullify_nans(pain_points.copy())
            pp.to_sql("fct_interaction_pain_point", con, if_exists="append", index=False)

        if not evidence.empty:
            # drop evidence whose rule_id is not in dim_rule (should be none)
            valid_rules = {
                r[0] for r in con.execute("SELECT rule_id FROM dim_rule").fetchall()
            }
            ev = evidence.loc[evidence["rule_id"].isin(valid_rules)].copy()
            ev = _nullify_nans(ev)
            if not ev.empty:
                ev.to_sql("fct_extraction_evidence", con, if_exists="append", index=False)

        con.commit()

        counts = {
            "fct_interaction": con.execute("SELECT COUNT(*) FROM fct_interaction").fetchone()[0],
            "fct_interaction_pain_point": con.execute(
                "SELECT COUNT(*) FROM fct_interaction_pain_point"
            ).fetchone()[0],
            "fct_extraction_evidence": con.execute(
                "SELECT COUNT(*) FROM fct_extraction_evidence"
            ).fetchone()[0],
        }
    finally:
        con.close()

    return {"db_path": str(db_path), **counts}


def export_fct_interaction(
    db_path: Path = DB_PATH,
    exports_dir: Path = EXPORTS_DIR,
) -> dict:
    exports_dir.mkdir(parents=True, exist_ok=True)
    con = init_db(db_path)
    try:
        df = pd.read_sql("SELECT * FROM fct_interaction", con)
    finally:
        con.close()

    csv_path = exports_dir / "fct_interaction.csv"
    df.to_csv(csv_path, index=False)

    parquet_path = exports_dir / "fct_interaction.parquet"
    try:
        df.to_parquet(parquet_path, index=False)
    except (ImportError, ValueError, OSError) as exc:
        # pyarrow/fastparquet may be missing (common on bare Anaconda)
        print(f"   parquet skipped ({exc.__class__.__name__}); wrote CSV only")
        parquet_path = None

    return {
        "rows": len(df),
        "parquet": str(parquet_path) if parquet_path else None,
        "csv": str(csv_path),
    }



def run_extract_score_load(db_path: Path = DB_PATH) -> dict:
    extracted = extract_all(db_path)
    scored = apply_scores(extracted)
    summary = load_facts(
        scored,
        extracted["pain_points"],
        extracted["evidence"],
        db_path=db_path,
        seed=True,
    )
    exports = export_fct_interaction(db_path)
    return {**summary, **exports}


if __name__ == "__main__":
    summary = run_extract_score_load()
    print(
        f"Loaded {summary['fct_interaction']:,} interactions, "
        f"{summary['fct_interaction_pain_point']:,} pain-point rows, "
        f"{summary['fct_extraction_evidence']:,} evidence rows"
    )
