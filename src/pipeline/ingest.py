"""Ingest CFPB complaints CSV into raw_complaints."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml

from src.paths import CONFIG_DIR, DB_PATH, DDL_PATH, DEFAULT_CSV

CONFIG_PATH = CONFIG_DIR / "scoring.yaml"

USECOLS = [
    "Complaint ID",
    "Date received",
    "Product",
    "Sub-product",
    "Issue",
    "Sub-issue",
    "Company",
    "State",
    "Consumer complaint narrative",
]

RENAME = {
    "Complaint ID": "complaint_id",
    "Date received": "date_received",
    "Product": "product",
    "Sub-product": "sub_product",
    "Issue": "issue",
    "Sub-issue": "sub_issue",
    "Company": "company",
    "State": "state",
    "Consumer complaint narrative": "consumer_complaint_narrative",
}


def load_config() -> dict:
    with CONFIG_PATH.open() as f:
        return yaml.safe_load(f)


def init_db(db_path: Path = DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(DDL_PATH.read_text())
    return con


def _filter_chunk(df: pd.DataFrame, products: list[str], min_date: pd.Timestamp) -> pd.DataFrame:
    df = df.rename(columns=RENAME)
    df["consumer_complaint_narrative"] = (
        df["consumer_complaint_narrative"].astype("string").str.strip()
    )
    mask = (
        df["consumer_complaint_narrative"].notna()
        & (df["consumer_complaint_narrative"] != "")
        & (df["product"].isin(products))
    )
    df = df.loc[mask].copy()
    if df.empty:
        return df

    df["date_received"] = pd.to_datetime(df["date_received"], errors="coerce")
    df = df.loc[df["date_received"].notna() & (df["date_received"] >= min_date)].copy()
    df["complaint_id"] = df["complaint_id"].astype(str)
    df["date_received"] = df["date_received"].dt.strftime("%Y-%m-%d")
    return df


def ingest_cfpb(
    csv_path: Path = DEFAULT_CSV,
    db_path: Path = DB_PATH,
    chunksize: int = 50_000,
) -> dict:
    if not csv_path.exists():
        raise FileNotFoundError(
            f"Missing CFPB CSV at {csv_path}. "
            "Download from https://www.consumerfinance.gov/data-research/consumer-complaints/"
        )

    cfg = load_config()["ingest"]
    products = cfg["products"]
    max_rows = int(cfg["max_rows"])
    lookback_years = int(cfg["lookback_years"])
    min_date = pd.Timestamp.today().normalize() - pd.DateOffset(years=lookback_years)
    loaded_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    con = init_db(db_path)
    try:
        con.execute("DELETE FROM raw_complaints")
        kept = 0
        chunks_seen = 0

        reader = pd.read_csv(
            csv_path,
            usecols=USECOLS,
            chunksize=chunksize,
            dtype=str,
            low_memory=True,
        )

        for chunk in reader:
            chunks_seen += 1
            filtered = _filter_chunk(chunk, products, min_date)
            if filtered.empty:
                continue

            remaining = max_rows - kept
            if remaining <= 0:
                break
            if len(filtered) > remaining:
                filtered = filtered.head(remaining)

            filtered["loaded_at"] = loaded_at
            filtered.to_sql("raw_complaints", con, if_exists="append", index=False)
            kept += len(filtered)

        con.commit()
    finally:
        con.close()

    return {
        "rows_loaded": kept,
        "chunks_read": chunks_seen,
        "db_path": str(db_path),
        "min_date": str(min_date.date()),
        "max_rows": max_rows,
    }


if __name__ == "__main__":
    summary = ingest_cfpb()
    print(
        f"Loaded {summary['rows_loaded']:,} complaints "
        f"(from {summary['chunks_read']} chunks) into {summary['db_path']}"
    )
