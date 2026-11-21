"""One-command rebuild: ingest -> clean -> extract/score/load -> quality -> insights."""

from __future__ import annotations

from pathlib import Path

from src.clean import stage_sentences
from src.ingest import DB_PATH, DEFAULT_CSV, ingest_cfpb
from src.insights import run_insights
from src.load import run_extract_score_load
from src.quality import run_quality_checks


def build(csv_path: Path = DEFAULT_CSV, db_path: Path = DB_PATH) -> None:
    print("1/5 ingest")
    ingest_summary = ingest_cfpb(csv_path=csv_path, db_path=db_path)
    print(f"   loaded {ingest_summary['rows_loaded']:,} complaints")

    print("2/5 clean")
    clean_summary = stage_sentences(db_path=db_path)
    print(f"   staged {clean_summary['sentences']:,} sentences")

    print("3/5 extract, score, load")
    load_summary = run_extract_score_load(db_path=db_path)
    print(f"   wrote {load_summary['fct_interaction']:,} rows to fct_interaction")
    print(f"   export CSV: {load_summary.get('csv')}")
    if load_summary.get("parquet"):
        print(f"   export parquet: {load_summary['parquet']}")

    print("4/5 quality checks")
    run_quality_checks(db_path=db_path, raise_on_fail=True)

    print("5/5 insights")
    run_insights(db_path=db_path)
    print("done")



if __name__ == "__main__":
    build()
