"""Seed dim_pain_point and dim_rule from schema + lexicon files."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

from src.pipeline.ingest import DB_PATH, init_db
from src.pipeline.schema import DIM_PAIN_POINT_SEED

from src.paths import LEXICON_DIR, SCORING_PATH


def _extractor_version() -> str:
    with SCORING_PATH.open() as f:
        return yaml.safe_load(f)["extractor_version"]


def _iter_rules(node, field_name: str | None = None):
    """Yield rule dicts from nested lexicon YAML."""
    if isinstance(node, list):
        for item in node:
            if isinstance(item, dict) and "rule_id" in item and "pattern" in item:
                yield {
                    "rule_id": item["rule_id"],
                    "field_name": field_name or item.get("field_name", "unknown"),
                    "pattern": item["pattern"],
                }
            else:
                yield from _iter_rules(item, field_name)
    elif isinstance(node, dict):
        # pain_points.yaml uses top-level field_name then code buckets
        top_field = node.get("field_name", field_name)
        for key, value in node.items():
            if key in {"field_name"}:
                continue
            next_field = top_field if top_field else key
            # channel buckets nest another level of lists
            if key == "channel" and isinstance(value, dict):
                for channel_name, rules in value.items():
                    yield from _iter_rules(rules, field_name="channel_primary")
            elif isinstance(value, (list, dict)):
                # For sentiment pos/neg etc., field is the key
                use_field = top_field if top_field and top_field != field_name else key
                if top_field == "primary_pain_point":
                    use_field = "primary_pain_point"
                yield from _iter_rules(value, field_name=use_field)


def load_rules_from_lexicons(version: str | None = None) -> pd.DataFrame:
    version = version or _extractor_version()
    rows: list[dict] = []
    seen: set[str] = set()

    for path in sorted(LEXICON_DIR.glob("*.yaml")):
        with path.open() as f:
            data = yaml.safe_load(f) or {}
        for rule in _iter_rules(data):
            rid = rule["rule_id"]
            if rid in seen:
                raise ValueError(f"Duplicate rule_id: {rid} in {path.name}")
            seen.add(rid)
            rows.append(
                {
                    "rule_id": rid,
                    "field_name": rule["field_name"],
                    "pattern": rule["pattern"],
                    "version_added": version,
                    "precision_on_labels": None,
                }
            )

    return pd.DataFrame(rows)


def seed_dimensions(db_path: Path = DB_PATH) -> dict:
    version = _extractor_version()
    pain = pd.DataFrame(DIM_PAIN_POINT_SEED)
    rules = load_rules_from_lexicons(version)

    con = init_db(db_path)
    try:
        # Child tables first when clearing (evidence/pain bridge reference dims)
        con.execute("DELETE FROM fct_extraction_evidence")
        con.execute("DELETE FROM fct_interaction_pain_point")
        con.execute("DELETE FROM dim_rule")
        con.execute("DELETE FROM dim_pain_point")
        pain.to_sql("dim_pain_point", con, if_exists="append", index=False)
        rules.to_sql("dim_rule", con, if_exists="append", index=False)
        con.commit()
    finally:
        con.close()

    return {
        "pain_points": len(pain),
        "rules": len(rules),
        "extractor_version": version,
        "db_path": str(db_path),
    }


if __name__ == "__main__":
    summary = seed_dimensions()
    print(
        f"Seeded {summary['pain_points']} pain points and "
        f"{summary['rules']} rules (v{summary['extractor_version']})"
    )
