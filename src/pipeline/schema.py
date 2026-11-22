"""Single source of truth for table columns, types, and allowed ranges."""

from __future__ import annotations

from typing import Any

PAIN_POINT_CODES = [
    "fees",
    "account_frozen_closed",
    "transfer_slow_failed",
    "fraud_unauthorized",
    "service_unreachable",
    "funds_held_missing",
    "digital_access",
    "promo_not_honored",
    "none",
]

FCT_INTERACTION_COLUMNS: list[dict[str, Any]] = [
    {"name": "interaction_id", "type": "TEXT", "nullable": False, "pk": True},
    {
        "name": "source",
        "type": "TEXT",
        "nullable": False,
        "allowed": ["cfpb_complaint", "call_transcript"],
    },
    {"name": "source_record_id", "type": "TEXT", "nullable": False},
    {"name": "interaction_date", "type": "DATE", "nullable": False},
    {"name": "product", "type": "TEXT", "nullable": True},
    {
        "name": "company_size_band",
        "type": "TEXT",
        "nullable": True,
        "allowed": ["top_10", "next_40", "long_tail"],
    },
    {"name": "state", "type": "TEXT", "nullable": True},
    {
        "name": "channel_primary",
        "type": "TEXT",
        "nullable": False,
        "allowed": ["phone", "branch", "app", "online", "email", "chat", "unknown"],
    },
    {"name": "word_count", "type": "INTEGER", "nullable": False, "min": 0},
    {"name": "redaction_share", "type": "REAL", "nullable": False, "min": 0.0, "max": 1.0},
    {"name": "n_turns", "type": "INTEGER", "nullable": True, "min": 1},
    {"name": "duration_sec", "type": "INTEGER", "nullable": True, "min": 0},
    {"name": "customer_talk_share", "type": "REAL", "nullable": True, "min": 0.0, "max": 1.0},
    {"name": "primary_pain_point", "type": "TEXT", "nullable": False},
    {"name": "pain_point_count", "type": "INTEGER", "nullable": False, "min": 0, "max": 8},
    {"name": "sentiment_score", "type": "REAL", "nullable": False, "min": -1.0, "max": 1.0},
    {
        "name": "sentiment_label",
        "type": "TEXT",
        "nullable": False,
        "allowed": ["negative", "neutral", "positive"],
    },
    {"name": "frustration_score", "type": "REAL", "nullable": False, "min": 0.0, "max": 1.0},
    {"name": "amount_usd_max", "type": "REAL", "nullable": True, "min": 0.0},
    {"name": "amount_mentions", "type": "INTEGER", "nullable": False, "min": 0},
    {"name": "delay_days_max", "type": "INTEGER", "nullable": True, "min": 0},
    {"name": "switching_intent", "type": "INTEGER", "nullable": False, "allowed": [0, 1]},
    {"name": "competitor_mentioned", "type": "INTEGER", "nullable": False, "allowed": [0, 1]},
    {"name": "escalation_flag", "type": "INTEGER", "nullable": False, "allowed": [0, 1]},
    {
        "name": "escalation_type",
        "type": "TEXT",
        "nullable": False,
        "allowed": ["legal", "regulator", "bbb", "media", "none"],
    },
    {"name": "severity_score", "type": "INTEGER", "nullable": False, "min": 0, "max": 100},
    {
        "name": "severity_band",
        "type": "TEXT",
        "nullable": False,
        "allowed": ["low", "medium", "high", "critical"],
    },
    {"name": "lead_signal_score", "type": "INTEGER", "nullable": False, "min": 0, "max": 100},
    {"name": "needs_review", "type": "INTEGER", "nullable": False, "allowed": [0, 1]},
    {
        "name": "review_reason",
        "type": "TEXT",
        "nullable": False,
        "allowed": [
            "no_pain_point",
            "high_redaction",
            "conflicting_rules",
            "too_short",
            "none",
        ],
    },
    {"name": "extractor_version", "type": "TEXT", "nullable": False},
    {"name": "extracted_at", "type": "TIMESTAMP", "nullable": False},
]

DIM_PAIN_POINT_SEED = [
    {"pain_point_code": "fees", "label": "Fees and charges", "challenger_addressable": 1},
    {
        "pain_point_code": "account_frozen_closed",
        "label": "Frozen or closed account",
        "challenger_addressable": 1,
    },
    {
        "pain_point_code": "transfer_slow_failed",
        "label": "Slow or failed transfer",
        "challenger_addressable": 1,
    },
    {
        "pain_point_code": "fraud_unauthorized",
        "label": "Fraud or unauthorized transaction",
        "challenger_addressable": 0,
    },
    {
        "pain_point_code": "service_unreachable",
        "label": "Poor service / can't reach anyone",
        "challenger_addressable": 1,
    },
    {
        "pain_point_code": "funds_held_missing",
        "label": "Deposit hold or missing funds",
        "challenger_addressable": 1,
    },
    {
        "pain_point_code": "digital_access",
        "label": "App or online access problems",
        "challenger_addressable": 1,
    },
    {
        "pain_point_code": "promo_not_honored",
        "label": "Interest, rewards or promotion not honored",
        "challenger_addressable": 1,
    },
]


def column_names(table: str = "fct_interaction") -> list[str]:
    if table != "fct_interaction":
        raise ValueError(f"Unknown table: {table}")
    return [c["name"] for c in FCT_INTERACTION_COLUMNS]
