"""Rule-based field extraction with sentence-level evidence."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import yaml

from src.clean import redaction_share, word_count
from src.ingest import DB_PATH, init_db

ROOT = Path(__file__).resolve().parents[1]
LEXICON_DIR = ROOT / "config" / "lexicons"
SCORING_PATH = ROOT / "config" / "scoring.yaml"

PAIN_POINT_CODES = [
    "fees",
    "account_frozen_closed",
    "transfer_slow_failed",
    "fraud_unauthorized",
    "service_unreachable",
    "funds_held_missing",
    "digital_access",
    "promo_not_honored",
]

ESCALATION_ORDER = ["legal", "regulator", "bbb", "media"]
CHANNEL_ORDER = ["phone", "branch", "app", "online", "email", "chat"]


@dataclass
class Rule:
    rule_id: str
    field_name: str
    pattern: str
    regex: bool = False
    group: str | None = None
    days: int | None = None
    unit: str | None = None
    compiled: re.Pattern = field(init=False, repr=False)

    def __post_init__(self) -> None:
        flags = re.IGNORECASE
        if self.regex:
            self.compiled = re.compile(self.pattern, flags)
        else:
            self.compiled = re.compile(re.escape(self.pattern), flags)


@dataclass
class Evidence:
    field_name: str
    rule_id: str
    sentence_no: int
    matched_text: str


def _load_yaml(name: str) -> dict:
    with (LEXICON_DIR / name).open() as f:
        return yaml.safe_load(f) or {}


def _as_rules(items: list, field_name: str, group: str | None = None) -> list[Rule]:
    rules = []
    for item in items or []:
        if not isinstance(item, dict) or "rule_id" not in item:
            continue
        rules.append(
            Rule(
                rule_id=item["rule_id"],
                field_name=field_name,
                pattern=item["pattern"],
                regex=bool(item.get("regex", False)),
                group=group,
                days=item.get("days"),
                unit=item.get("unit"),
            )
        )
    return rules


def load_lexicons() -> dict[str, list[Rule]]:
    pain_raw = _load_yaml("pain_points.yaml")
    pain_rules: list[Rule] = []
    for code in PAIN_POINT_CODES:
        pain_rules.extend(_as_rules(pain_raw.get(code, []), "primary_pain_point", group=code))

    switching = _load_yaml("switching.yaml")
    sentiment = _load_yaml("sentiment.yaml")
    escalation = _load_yaml("escalation.yaml")
    amounts = _load_yaml("amounts_delays.yaml")

    channel_rules: list[Rule] = []
    for channel, items in (amounts.get("channel") or {}).items():
        channel_rules.extend(_as_rules(items, "channel_primary", group=channel))

    return {
        "pain_points": pain_rules,
        "switching_intent": _as_rules(switching.get("switching_intent", []), "switching_intent"),
        "competitor_mentioned": _as_rules(
            switching.get("competitor_mentioned", []), "competitor_mentioned"
        ),
        "positive": _as_rules(sentiment.get("positive", []), "sentiment_score"),
        "negative": _as_rules(sentiment.get("negative", []), "sentiment_score"),
        "frustration_phrases": _as_rules(
            sentiment.get("frustration_phrases", []), "frustration_score"
        ),
        "repeated_contact": _as_rules(
            sentiment.get("repeated_contact", []), "frustration_score"
        ),
        "negation": sentiment.get("negation", ["not", "never", "no", "n't"]),
        "escalation": [
            rule
            for esc_type in ESCALATION_ORDER
            for rule in _as_rules(escalation.get(esc_type, []), "escalation_type", group=esc_type)
        ],
        "amount": _as_rules(amounts.get("amount", []), "amount_usd_max"),
        "delay": _as_rules(amounts.get("delay", []), "delay_days_max"),
        "channel": channel_rules,
    }


def _match_rules(sentences: list[tuple[int, str]], rules: list[Rule]) -> list[tuple[Rule, Evidence, re.Match]]:
    hits = []
    for sentence_no, text in sentences:
        for rule in rules:
            for m in rule.compiled.finditer(text):
                hits.append(
                    (
                        rule,
                        Evidence(
                            field_name=rule.field_name,
                            rule_id=rule.rule_id,
                            sentence_no=sentence_no,
                            matched_text=m.group(0)[:200],
                        ),
                        m,
                    )
                )
    return hits


def _parse_amount(match: re.Match, rule: Rule) -> float | None:
    raw = match.group(1) if match.lastindex else match.group(0)
    raw = raw.replace(",", "").replace("$", "").strip()
    try:
        value = float(raw)
    except ValueError:
        return None
    if rule.rule_id == "AMT-03" or raw.lower().endswith("k"):
        # "5k" style — group is the number before k
        value *= 1000
    return value


def _parse_delay_days(match: re.Match, rule: Rule) -> int | None:
    if rule.days is not None:
        return int(rule.days)
    if not match.lastindex:
        return None
    try:
        n = int(match.group(1))
    except ValueError:
        return None
    unit = (rule.unit or "days").lower()
    if unit == "weeks":
        return n * 7
    if unit == "months":
        return n * 30
    return n


def extract_pain_points(sentences: list[tuple[int, str]], lex: dict) -> tuple[str, int, list[dict], list[Evidence]]:
    hits = _match_rules(sentences, lex["pain_points"])
    counts: dict[str, int] = {}
    evidence: list[Evidence] = []
    for rule, ev, _ in hits:
        code = rule.group or "none"
        counts[code] = counts.get(code, 0) + 1
        evidence.append(ev)

    if not counts:
        return "none", 0, [], evidence

    primary = max(counts.items(), key=lambda kv: (kv[1], kv[0]))[0]
    bridge = [
        {
            "pain_point_code": code,
            "is_primary": 1 if code == primary else 0,
            "match_count": n,
        }
        for code, n in sorted(counts.items())
    ]
    return primary, len(counts), bridge, evidence


def extract_binary_flag(sentences: list[tuple[int, str]], rules: list[Rule]) -> tuple[int, list[Evidence]]:
    hits = _match_rules(sentences, rules)
    return (1 if hits else 0), [ev for _, ev, _ in hits]


def extract_escalation(sentences: list[tuple[int, str]], lex: dict) -> tuple[int, str, list[Evidence]]:
    hits = _match_rules(sentences, lex["escalation"])
    if not hits:
        return 0, "none", []
    # first type in priority order that appears
    seen_types = {rule.group for rule, _, _ in hits}
    esc_type = next((t for t in ESCALATION_ORDER if t in seen_types), "none")
    evidence = [ev for _, ev, _ in hits if True]
    return 1, esc_type, evidence


def extract_channel(sentences: list[tuple[int, str]], lex: dict) -> tuple[str, list[Evidence]]:
    hits = _match_rules(sentences, lex["channel"])
    if not hits:
        return "unknown", []
    counts: dict[str, int] = {}
    evidence = []
    for rule, ev, _ in hits:
        ch = rule.group or "unknown"
        counts[ch] = counts.get(ch, 0) + 1
        evidence.append(ev)
    primary = max(counts.items(), key=lambda kv: (kv[1], -CHANNEL_ORDER.index(kv[0]) if kv[0] in CHANNEL_ORDER else 0))[0]
    return primary, evidence


def extract_amounts(sentences: list[tuple[int, str]], lex: dict) -> tuple[float | None, int, list[Evidence]]:
    hits = _match_rules(sentences, lex["amount"])
    values = []
    evidence = []
    for rule, ev, match in hits:
        amount = _parse_amount(match, rule)
        if amount is not None and amount >= 0:
            values.append(amount)
            evidence.append(ev)
    if not values:
        return None, 0, []
    return max(values), len(values), evidence


def extract_delay(sentences: list[tuple[int, str]], lex: dict) -> tuple[int | None, list[Evidence]]:
    hits = _match_rules(sentences, lex["delay"])
    days_list = []
    evidence = []
    for rule, ev, match in hits:
        days = _parse_delay_days(match, rule)
        if days is not None and days >= 0:
            days_list.append(days)
            evidence.append(ev)
    if not days_list:
        return None, []
    return max(days_list), evidence


def review_flags(
    primary_pain_point: str,
    word_count_val: int,
    redaction_share_val: float,
    cfg: dict,
) -> tuple[int, str]:
    # Flag uncertain text only. primary_pain_point == none is allowed without
    # forcing review — many complaints simply don't match the lexicon.
    review = cfg.get("review", {})
    if word_count_val < int(review.get("too_short_words", 20)):
        return 1, "too_short"
    if redaction_share_val >= float(review.get("high_redaction_share", 0.35)):
        return 1, "high_redaction"
    return 0, "none"


def company_size_bands(companies: pd.Series) -> pd.Series:
    """Rank companies by complaint volume into top_10 / next_40 / long_tail."""
    counts = companies.fillna("UNKNOWN").value_counts()
    rank = {name: i + 1 for i, name in enumerate(counts.index)}

    def band(name: str) -> str:
        r = rank.get(name if pd.notna(name) else "UNKNOWN", 10_000)
        if r <= 10:
            return "top_10"
        if r <= 50:
            return "next_40"
        return "long_tail"

    return companies.map(band)


def extract_interaction(
    interaction_id: str,
    sentences: list[tuple[int, str]],
    lex: dict | None = None,
    scoring_cfg: dict | None = None,
) -> dict:
    lex = lex or load_lexicons()
    scoring_cfg = scoring_cfg or yaml.safe_load(SCORING_PATH.read_text())

    full_text = " ".join(text for _, text in sentences)
    wc = word_count(full_text)
    rs = redaction_share(full_text)

    primary, pain_count, bridge, pain_ev = extract_pain_points(sentences, lex)
    switching, sw_ev = extract_binary_flag(sentences, lex["switching_intent"])
    competitor, cmp_ev = extract_binary_flag(sentences, lex["competitor_mentioned"])
    esc_flag, esc_type, esc_ev = extract_escalation(sentences, lex)
    channel, ch_ev = extract_channel(sentences, lex)
    amount_max, amount_n, amt_ev = extract_amounts(sentences, lex)
    delay_max, dly_ev = extract_delay(sentences, lex)
    needs_review, review_reason = review_flags(primary, wc, rs, scoring_cfg)

    evidence = pain_ev + sw_ev + cmp_ev + esc_ev + ch_ev + amt_ev + dly_ev
    # keep evidence only for non-default / informative fields
    filtered_evidence = []
    for ev in evidence:
        if ev.field_name == "channel_primary" and channel == "unknown":
            continue
        filtered_evidence.append(ev)

    return {
        "interaction_id": interaction_id,
        "channel_primary": channel,
        "word_count": wc,
        "redaction_share": rs,
        "primary_pain_point": primary,
        "pain_point_count": pain_count,
        "amount_usd_max": amount_max,
        "amount_mentions": amount_n,
        "delay_days_max": delay_max,
        "switching_intent": switching,
        "competitor_mentioned": competitor,
        "escalation_flag": esc_flag,
        "escalation_type": esc_type,
        "needs_review": needs_review,
        "review_reason": review_reason,
        "pain_point_rows": bridge,
        "evidence": filtered_evidence,
        "lexicon_hits": {
            "positive": _match_rules(sentences, lex["positive"]),
            "negative": _match_rules(sentences, lex["negative"]),
            "frustration_phrases": _match_rules(sentences, lex["frustration_phrases"]),
            "repeated_contact": _match_rules(sentences, lex["repeated_contact"]),
            "negation": lex["negation"],
            "full_text": full_text,
        },
    }


def extract_all(db_path: Path = DB_PATH) -> dict:
    """Extract fields for every staged interaction. Returns dataframes + hit payloads for scoring."""
    lex = load_lexicons()
    scoring_cfg = yaml.safe_load(SCORING_PATH.read_text())

    con = init_db(db_path)
    try:
        sentences_df = pd.read_sql(
            """
            SELECT interaction_id, sentence_no, sentence_text
            FROM stg_sentences
            ORDER BY interaction_id, sentence_no
            """,
            con,
        )
        raw = pd.read_sql(
            """
            SELECT complaint_id, date_received, product, company, state
            FROM raw_complaints
            """,
            con,
        )
    finally:
        con.close()

    if sentences_df.empty:
        raise ValueError("stg_sentences is empty — run clean first")

    raw["interaction_id"] = "CFPB-" + raw["complaint_id"].astype(str)
    raw["company_size_band"] = company_size_bands(raw["company"])

    grouped = {
        iid: list(zip(g["sentence_no"].tolist(), g["sentence_text"].tolist()))
        for iid, g in sentences_df.groupby("interaction_id", sort=False)
    }

    records = []
    pain_rows = []
    evidence_rows = []
    score_inputs = {}

    for interaction_id, sents in grouped.items():
        result = extract_interaction(interaction_id, sents, lex=lex, scoring_cfg=scoring_cfg)
        score_inputs[interaction_id] = result.pop("lexicon_hits")
        bridge = result.pop("pain_point_rows")
        evidence = result.pop("evidence")

        meta = raw.loc[raw["interaction_id"] == interaction_id]
        if meta.empty:
            continue
        row = meta.iloc[0]
        result.update(
            {
                "source": "cfpb_complaint",
                "source_record_id": str(row["complaint_id"]),
                "interaction_date": row["date_received"],
                "product": row["product"],
                "company_size_band": row["company_size_band"],
                "state": row["state"],
                "n_turns": None,
                "duration_sec": None,
                "customer_talk_share": None,
            }
        )
        records.append(result)

        for b in bridge:
            pain_rows.append({"interaction_id": interaction_id, **b})
        for ev in evidence:
            evidence_rows.append(
                {
                    "interaction_id": interaction_id,
                    "field_name": ev.field_name,
                    "rule_id": ev.rule_id,
                    "sentence_no": ev.sentence_no,
                    "matched_text": ev.matched_text,
                }
            )

    return {
        "interactions": pd.DataFrame(records),
        "pain_points": pd.DataFrame(pain_rows),
        "evidence": pd.DataFrame(evidence_rows),
        "score_inputs": score_inputs,
        "scoring_cfg": scoring_cfg,
    }


if __name__ == "__main__":
    out = extract_all()
    df = out["interactions"]
    print(f"Extracted {len(df):,} interactions")
    print(df["primary_pain_point"].value_counts().head(10).to_string())
    print(f"switching_intent rate: {df['switching_intent'].mean():.3f}")
