"""Repo-root paths used across the pipeline."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CONFIG_DIR = ROOT / "config"
SCORING_PATH = CONFIG_DIR / "scoring.yaml"
LEXICON_DIR = CONFIG_DIR / "lexicons"

DATA_DIR = ROOT / "data"
DEFAULT_CSV = DATA_DIR / "raw" / "complaints.csv"
LABELS_PATH = DATA_DIR / "labels" / "labels.csv"
LABELS_TEMPLATE_PATH = DATA_DIR / "labels" / "labels_template.csv"

SQL_DIR = ROOT / "sql"
DDL_PATH = SQL_DIR / "ddl.sql"
ANALYSIS_SQL_DIR = SQL_DIR / "analysis"

OUTPUT_DIR = ROOT / "output"
DB_PATH = OUTPUT_DIR / "signals.db"
EXPORTS_DIR = OUTPUT_DIR / "exports"
FIGURES_DIR = OUTPUT_DIR / "figures"
