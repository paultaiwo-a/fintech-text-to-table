"""Post-load data quality checks for the interaction tables."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import yaml

from src.ingest import DB_PATH, init_db

ROOT = Path(__file__).resolve().parents[1]
SCORING_PATH = ROOT / "config" / "scoring.yaml"

SEVERITY_BANDS = {
    "low": (0, 24),
    "medium": (25, 49),
    "high": (50, 74),
    "critical": (75, 100),
}


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str


def _max_needs_review_share() -> float:
    with SCORING_PATH.open() as f:
        return float(yaml.safe_load(f)["review"]["max_needs_review_share"])


def check_row_count_matches_staging(con) -> CheckResult:
    fct = con.execute("SELECT COUNT(*) FROM fct_interaction").fetchone()[0]
    stg = con.execute("SELECT COUNT(DISTINCT interaction_id) FROM stg_sentences").fetchone()[0]
    ok = fct == stg
    return CheckResult(
        "row_count_matches_staging",
        ok,
        f"fct_interaction={fct:,}, distinct stg_sentences={stg:,}",
    )


def check_no_duplicate_ids(con) -> CheckResult:
    dupes = con.execute(
        """
        SELECT COUNT(*) FROM (
          SELECT interaction_id
          FROM fct_interaction
          GROUP BY interaction_id
          HAVING COUNT(*) > 1
        )
        """
    ).fetchone()[0]
    return CheckResult(
        "no_duplicate_interaction_id",
        dupes == 0,
        f"duplicate_ids={dupes}",
    )


def check_switching_has_evidence(con) -> CheckResult:
    missing = con.execute(
        """
        SELECT COUNT(*)
        FROM fct_interaction f
        WHERE f.switching_intent = 1
          AND NOT EXISTS (
            SELECT 1
            FROM fct_extraction_evidence e
            WHERE e.interaction_id = f.interaction_id
              AND e.field_name = 'switching_intent'
          )
        """
    ).fetchone()[0]
    return CheckResult(
        "switching_intent_has_evidence",
        missing == 0,
        f"switching_rows_missing_evidence={missing}",
    )


def check_severity_band_matches_score(con) -> CheckResult:
    df = pd.read_sql(
        "SELECT interaction_id, severity_score, severity_band FROM fct_interaction",
        con,
    )
    if df.empty:
        return CheckResult("severity_band_matches_score", True, "no rows")

    def expected_band(score: int) -> str:
        for name, (lo, hi) in SEVERITY_BANDS.items():
            if lo <= int(score) <= hi:
                return name
        return "invalid"

    df["expected"] = df["severity_score"].map(expected_band)
    bad = int((df["severity_band"] != df["expected"]).sum())
    return CheckResult(
        "severity_band_matches_score",
        bad == 0,
        f"mismatched_rows={bad}",
    )


def check_needs_review_share(con) -> CheckResult:
    threshold = _max_needs_review_share()
    row = con.execute(
        """
        SELECT
          AVG(needs_review * 1.0) AS share,
          COUNT(*) AS n
        FROM fct_interaction
        """
    ).fetchone()
    share = float(row[0] or 0.0)
    ok = share <= threshold
    return CheckResult(
        "needs_review_share_under_threshold",
        ok,
        f"share={share:.3f}, threshold={threshold:.3f}, n={row[1]:,}",
    )


def check_pain_points_in_dim(con) -> CheckResult:
    missing = con.execute(
        """
        SELECT COUNT(*)
        FROM fct_interaction_pain_point p
        WHERE NOT EXISTS (
          SELECT 1 FROM dim_pain_point d
          WHERE d.pain_point_code = p.pain_point_code
        )
        """
    ).fetchone()[0]
    # also primary_pain_point on fact (allow 'none')
    bad_primary = con.execute(
        """
        SELECT COUNT(*)
        FROM fct_interaction f
        WHERE f.primary_pain_point != 'none'
          AND NOT EXISTS (
            SELECT 1 FROM dim_pain_point d
            WHERE d.pain_point_code = f.primary_pain_point
          )
        """
    ).fetchone()[0]
    total_bad = missing + bad_primary
    return CheckResult(
        "pain_point_codes_in_dim",
        total_bad == 0,
        f"bridge_missing={missing}, primary_missing={bad_primary}",
    )


DEFAULT_CHECKS = [
    check_row_count_matches_staging,
    check_no_duplicate_ids,
    check_switching_has_evidence,
    check_severity_band_matches_score,
    check_needs_review_share,
    check_pain_points_in_dim,
]


def run_quality_checks(db_path: Path = DB_PATH, raise_on_fail: bool = True) -> list[CheckResult]:
    con = init_db(db_path)
    try:
        results = [check(con) for check in DEFAULT_CHECKS]
    finally:
        con.close()

    failed = [r for r in results if not r.passed]
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        print(f"[{status}] {r.name}: {r.detail}")

    if failed and raise_on_fail:
        names = ", ".join(r.name for r in failed)
        raise AssertionError(f"Data quality checks failed: {names}")
    return results


if __name__ == "__main__":
    run_quality_checks(raise_on_fail=True)
