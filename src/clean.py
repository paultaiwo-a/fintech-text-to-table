"""Clean complaint narratives and stage sentences for evidence linking."""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import pandas as pd

from src.ingest import DB_PATH, init_db

REDACTION_PATTERNS = [
    (re.compile(r"\bX{2,}\b", re.IGNORECASE), "<redacted>"),
    (re.compile(r"\bXX+/\w{2,}/\w{2,}\b"), "<date>"),
    (re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b"), "<date>"),
]

WHITESPACE_RE = re.compile(r"\s+")
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])")
TOKEN_RE = re.compile(r"\S+")


def clean_text(text: str) -> str:
    if text is None or (isinstance(text, float) and pd.isna(text)):
        return ""
    out = str(text).replace("\xa0", " ").strip()
    for pattern, repl in REDACTION_PATTERNS:
        out = pattern.sub(repl, out)
    out = WHITESPACE_RE.sub(" ", out).strip()
    return out


def split_sentences(text: str) -> list[str]:
    text = clean_text(text)
    if not text:
        return []
    parts = SENTENCE_RE.split(text)
    return [p.strip() for p in parts if p.strip()]


def word_count(text: str) -> int:
    return len(TOKEN_RE.findall(clean_text(text)))


def redaction_share(text: str) -> float:
    cleaned = clean_text(text)
    tokens = TOKEN_RE.findall(cleaned)
    if not tokens:
        return 0.0
    redacted = sum(1 for t in tokens if t.lower() in {"<redacted>", "<date>", "xxxx"})
    # raw XXXX may remain if short; count x-only tokens too
    redacted += sum(
        1
        for t in tokens
        if re.fullmatch(r"x{2,}", t, flags=re.IGNORECASE)
    )
    return round(min(1.0, redacted / len(tokens)), 4)


def stage_sentences(db_path: Path = DB_PATH) -> dict:
    con = init_db(db_path)
    try:
        raw = pd.read_sql(
            """
            SELECT complaint_id, consumer_complaint_narrative
            FROM raw_complaints
            """,
            con,
        )
        if raw.empty:
            raise ValueError("raw_complaints is empty — run ingest first")

        rows: list[dict] = []
        for complaint_id, narrative in raw.itertuples(index=False):
            interaction_id = f"CFPB-{complaint_id}"
            for i, sentence in enumerate(split_sentences(narrative), start=1):
                rows.append(
                    {
                        "interaction_id": interaction_id,
                        "sentence_no": i,
                        "sentence_text": sentence,
                    }
                )

        sentences = pd.DataFrame(rows)
        con.execute("DELETE FROM stg_sentences")
        sentences.to_sql("stg_sentences", con, if_exists="append", index=False)
        con.commit()
    finally:
        con.close()

    return {
        "interactions": int(raw["complaint_id"].nunique()),
        "sentences": len(sentences),
        "db_path": str(db_path),
    }


def load_interaction_text(con: sqlite3.Connection) -> pd.DataFrame:
    """Rebuild cleaned full text from staged sentences (order preserved)."""
    sentences = pd.read_sql(
        """
        SELECT interaction_id, sentence_no, sentence_text
        FROM stg_sentences
        ORDER BY interaction_id, sentence_no
        """,
        con,
    )
    if sentences.empty:
        return pd.DataFrame(
            columns=["interaction_id", "cleaned_text", "n_sentences", "word_count", "redaction_share"]
        )

    df = (
        sentences.groupby("interaction_id", sort=False)
        .agg(
            cleaned_text=("sentence_text", lambda s: " ".join(s)),
            n_sentences=("sentence_no", "size"),
        )
        .reset_index()
    )
    df["word_count"] = df["cleaned_text"].map(word_count)
    df["redaction_share"] = df["cleaned_text"].map(redaction_share)
    return df


if __name__ == "__main__":
    summary = stage_sentences()
    print(
        f"Staged {summary['sentences']:,} sentences "
        f"across {summary['interactions']:,} interactions"
    )
