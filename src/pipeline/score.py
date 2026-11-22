"""Sentiment, frustration, severity, and lead-signal scores."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import pandas as pd
import yaml

from src.pipeline.schema import DIM_PAIN_POINT_SEED

from src.paths import SCORING_PATH

TOKEN_RE = re.compile(r"\S+")
EXCLAIM_OR_CAPS_RE = re.compile(r"!|(?:\b[A-Z]{3,}\b)")

ADDRESSABLE = {
    row["pain_point_code"]: int(row["challenger_addressable"])
    for row in DIM_PAIN_POINT_SEED
}


def load_scoring_config() -> dict:
    with SCORING_PATH.open() as f:
        return yaml.safe_load(f)


def _token_spans(text: str) -> list[tuple[str, int, int]]:
    return [(m.group(0), m.start(), m.end()) for m in TOKEN_RE.finditer(text)]


def _negated(tokens: list[str], hit_index: int, negation_words: list[str], window: int) -> bool:
    start = max(0, hit_index - window)
    window_tokens = [t.lower().strip(".,;:!?\"'") for t in tokens[start:hit_index]]
    neg = {n.lower() for n in negation_words}
    return any(t in neg or t.endswith("n't") for t in window_tokens)


def _lexicon_hit_indices(text: str, rules: list) -> list[int]:
    """Return token index for each lexicon match in text."""
    spans = _token_spans(text)
    tokens = [t for t, _, _ in spans]
    hit_indices = []
    for rule, _ev, match in rules:
        start_char = match.start()
        for i, (_tok, s, e) in enumerate(spans):
            if s <= start_char < e or (start_char <= s and e <= match.end()):
                hit_indices.append(i)
                break
            if s >= match.end():
                break
    return hit_indices, tokens


def sentiment_score(
    text: str,
    positive_hits: list,
    negative_hits: list,
    negation_words: list[str],
    cfg: dict,
) -> tuple[float, str]:
    sent_cfg = cfg["sentiment"]
    window = int(sent_cfg["negation_window"])

    pos_idx, tokens = _lexicon_hit_indices(text, positive_hits)
    neg_idx, _ = _lexicon_hit_indices(text, negative_hits)

    pos = 0
    neg = 0
    for i in pos_idx:
        if _negated(tokens, i, negation_words, window):
            neg += 1
        else:
            pos += 1
    for i in neg_idx:
        if _negated(tokens, i, negation_words, window):
            pos += 1
        else:
            neg += 1

    score = (pos - neg) / (pos + neg + 1)
    score = max(-1.0, min(1.0, round(score, 4)))

    if score <= float(sent_cfg["negative_threshold"]):
        label = "negative"
    elif score >= float(sent_cfg["positive_threshold"]):
        label = "positive"
    else:
        label = "neutral"
    return score, label


def frustration_score(
    text: str,
    phrase_hits: list,
    repeated_hits: list,
    sentiment: float,
    cfg: dict,
) -> float:
    f = cfg["frustration"]
    phrase_n = min(len(phrase_hits), int(f["phrase_cap"]))
    repeated = 1 if repeated_hits else 0
    caps = 1 if EXCLAIM_OR_CAPS_RE.search(text or "") else 0
    very_neg = 1 if sentiment <= float(f["very_negative_sentiment"]) else 0

    score = min(
        1.0,
        float(f["phrase_weight"]) * phrase_n / int(f["phrase_cap"])
        + float(f["repeated_contact_weight"]) * repeated
        + float(f["exclamation_or_caps_weight"]) * caps
        + float(f["very_negative_weight"]) * very_neg,
    )
    return round(score, 4)


def severity_score(
    amount: float | None,
    delay_days: int | None,
    escalation_flag: int,
    switching_intent: int,
    sentiment: float,
    cfg: dict,
) -> tuple[int, str]:
    s = cfg["severity"]
    ap = s["amount_points"]
    dp = s["delay_points"]

    if amount is None:
        amount_pts = ap["none"]
    elif amount < 100:
        amount_pts = ap["under_100"]
    elif amount < 1000:
        amount_pts = ap["from_100_to_999"]
    elif amount < 10_000:
        amount_pts = ap["from_1000_to_9999"]
    else:
        amount_pts = ap["from_10000_plus"]

    if delay_days is None:
        delay_pts = dp["none"]
    elif delay_days < 7:
        delay_pts = dp["under_7_days"]
    elif delay_days < 30:
        delay_pts = dp["from_7_to_29_days"]
    else:
        delay_pts = dp["from_30_days_plus"]

    total = (
        int(amount_pts)
        + int(delay_pts)
        + int(s["escalation_points"]) * int(escalation_flag)
        + int(s["switching_intent_points"]) * int(switching_intent)
        + (
            int(s["very_negative_sentiment_points"])
            if sentiment <= float(s["very_negative_sentiment"])
            else 0
        )
    )
    total = max(0, min(100, total))

    bands = s["bands"]
    band = "low"
    for name, (lo, hi) in bands.items():
        if lo <= total <= hi:
            band = name
            break
    return total, band


def lead_signal_score(
    switching_intent: int,
    primary_pain_point: str,
    amount: float | None,
    competitor_mentioned: int,
    interaction_date: str | pd.Timestamp | None,
    max_date: pd.Timestamp,
    cfg: dict,
) -> int:
    ls = cfg["lead_signal"]
    score = 0
    score += int(ls["switching_intent_points"]) * int(switching_intent)
    if ADDRESSABLE.get(primary_pain_point, 0) == 1:
        score += int(ls["challenger_addressable_points"])
    if amount is not None and amount >= float(ls["amount_threshold_usd"]):
        score += int(ls["amount_points"])
    score += int(ls["competitor_mentioned_points"]) * int(competitor_mentioned)

    if interaction_date is not None and pd.notna(interaction_date):
        dt = pd.Timestamp(interaction_date)
        if (max_date - dt).days <= int(ls["recent_days"]):
            score += int(ls["recent_points"])

    return max(0, min(100, int(score)))


def score_interaction(
    row: dict,
    lexicon_hits: dict,
    cfg: dict,
    max_date: pd.Timestamp,
) -> dict:
    text = lexicon_hits.get("full_text", "")
    sent, label = sentiment_score(
        text,
        lexicon_hits.get("positive", []),
        lexicon_hits.get("negative", []),
        lexicon_hits.get("negation", []),
        cfg,
    )
    frust = frustration_score(
        text,
        lexicon_hits.get("frustration_phrases", []),
        lexicon_hits.get("repeated_contact", []),
        sent,
        cfg,
    )
    sev, band = severity_score(
        row.get("amount_usd_max"),
        row.get("delay_days_max"),
        row.get("escalation_flag", 0),
        row.get("switching_intent", 0),
        sent,
        cfg,
    )
    lead = lead_signal_score(
        row.get("switching_intent", 0),
        row.get("primary_pain_point", "none"),
        row.get("amount_usd_max"),
        row.get("competitor_mentioned", 0),
        row.get("interaction_date"),
        max_date,
        cfg,
    )
    return {
        "sentiment_score": sent,
        "sentiment_label": label,
        "frustration_score": frust,
        "severity_score": sev,
        "severity_band": band,
        "lead_signal_score": lead,
        "extractor_version": cfg["extractor_version"],
        "extracted_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def apply_scores(extract_result: dict) -> pd.DataFrame:
    """Add score columns to the interactions frame from extract_all()."""
    cfg = extract_result.get("scoring_cfg") or load_scoring_config()
    interactions = extract_result["interactions"].copy()
    score_inputs = extract_result["score_inputs"]

    if interactions.empty:
        return interactions

    max_date = pd.to_datetime(interactions["interaction_date"]).max()
    scored_rows = []
    for row in interactions.to_dict(orient="records"):
        iid = row["interaction_id"]
        scored = score_interaction(row, score_inputs.get(iid, {}), cfg, max_date)
        scored_rows.append(scored)

    scored_df = pd.DataFrame(scored_rows)
    return pd.concat([interactions.reset_index(drop=True), scored_df], axis=1)


if __name__ == "__main__":
    from src.pipeline.extract import extract_interaction, load_lexicons

    lex = load_lexicons()
    cfg = load_scoring_config()
    sents = [
        (1, "I called five times about an overdraft fee of $4200."),
        (2, "The transfer never went through after 21 days."),
        (3, "I am closing my account and moving my money to another bank."),
        (4, "This is ridiculous and unacceptable. I will contact a lawyer."),
    ]
    extracted = extract_interaction("CFPB-1", sents, lex=lex, scoring_cfg=cfg)
    hits = extracted.pop("lexicon_hits")
    extracted.pop("pain_point_rows")
    extracted.pop("evidence")
    extracted["interaction_date"] = "2024-06-01"
    scores = score_interaction(extracted, hits, cfg, pd.Timestamp("2024-08-01"))
    print(scores)
