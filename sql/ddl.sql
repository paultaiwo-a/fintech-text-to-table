-- Schema for unstructured text -> analytics tables.
-- Create these before loading so CHECK constraints enforce the contract.

CREATE TABLE IF NOT EXISTS raw_complaints (
  complaint_id              TEXT PRIMARY KEY,
  date_received             DATE NOT NULL,
  product                   TEXT,
  sub_product               TEXT,
  issue                     TEXT,
  sub_issue                 TEXT,
  company                   TEXT,
  state                     TEXT,
  consumer_complaint_narrative TEXT NOT NULL,
  loaded_at                 TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS stg_sentences (
  interaction_id  TEXT NOT NULL,
  sentence_no     INTEGER NOT NULL,
  sentence_text   TEXT NOT NULL,
  PRIMARY KEY (interaction_id, sentence_no)
);

CREATE TABLE IF NOT EXISTS dim_pain_point (
  pain_point_code         TEXT PRIMARY KEY,
  label                   TEXT NOT NULL,
  challenger_addressable  INTEGER NOT NULL CHECK (challenger_addressable IN (0, 1))
);

CREATE TABLE IF NOT EXISTS dim_rule (
  rule_id                 TEXT PRIMARY KEY,
  field_name              TEXT NOT NULL,
  pattern                 TEXT NOT NULL,
  version_added           TEXT NOT NULL,
  precision_on_labels     REAL
);

CREATE TABLE IF NOT EXISTS fct_interaction (
  interaction_id        TEXT PRIMARY KEY,
  source                TEXT NOT NULL CHECK (source IN ('cfpb_complaint', 'call_transcript')),
  source_record_id      TEXT NOT NULL,
  interaction_date      DATE NOT NULL,
  product               TEXT,
  company_size_band     TEXT CHECK (company_size_band IN ('top_10', 'next_40', 'long_tail')),
  state                 TEXT,
  channel_primary       TEXT NOT NULL CHECK (channel_primary IN
                          ('phone', 'branch', 'app', 'online', 'email', 'chat', 'unknown')),
  word_count            INTEGER NOT NULL CHECK (word_count >= 0),
  redaction_share       REAL NOT NULL CHECK (redaction_share BETWEEN 0 AND 1),
  n_turns               INTEGER CHECK (n_turns >= 1),
  duration_sec          INTEGER CHECK (duration_sec >= 0),
  customer_talk_share   REAL CHECK (customer_talk_share BETWEEN 0 AND 1),
  primary_pain_point    TEXT NOT NULL,
  pain_point_count      INTEGER NOT NULL CHECK (pain_point_count BETWEEN 0 AND 8),
  sentiment_score       REAL NOT NULL CHECK (sentiment_score BETWEEN -1 AND 1),
  sentiment_label       TEXT NOT NULL CHECK (sentiment_label IN ('negative', 'neutral', 'positive')),
  frustration_score     REAL NOT NULL CHECK (frustration_score BETWEEN 0 AND 1),
  amount_usd_max        REAL CHECK (amount_usd_max >= 0),
  amount_mentions       INTEGER NOT NULL CHECK (amount_mentions >= 0),
  delay_days_max        INTEGER CHECK (delay_days_max >= 0),
  switching_intent      INTEGER NOT NULL CHECK (switching_intent IN (0, 1)),
  competitor_mentioned  INTEGER NOT NULL CHECK (competitor_mentioned IN (0, 1)),
  escalation_flag       INTEGER NOT NULL CHECK (escalation_flag IN (0, 1)),
  escalation_type       TEXT NOT NULL CHECK (escalation_type IN
                          ('legal', 'regulator', 'bbb', 'media', 'none')),
  severity_score        INTEGER NOT NULL CHECK (severity_score BETWEEN 0 AND 100),
  severity_band         TEXT NOT NULL CHECK (severity_band IN ('low', 'medium', 'high', 'critical')),
  lead_signal_score     INTEGER NOT NULL CHECK (lead_signal_score BETWEEN 0 AND 100),
  needs_review          INTEGER NOT NULL CHECK (needs_review IN (0, 1)),
  review_reason         TEXT NOT NULL,
  extractor_version     TEXT NOT NULL,
  extracted_at          TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS fct_interaction_pain_point (
  interaction_id   TEXT NOT NULL REFERENCES fct_interaction (interaction_id),
  pain_point_code  TEXT NOT NULL REFERENCES dim_pain_point (pain_point_code),
  is_primary       INTEGER NOT NULL CHECK (is_primary IN (0, 1)),
  match_count      INTEGER NOT NULL CHECK (match_count >= 1),
  PRIMARY KEY (interaction_id, pain_point_code)
);

CREATE TABLE IF NOT EXISTS fct_extraction_evidence (
  evidence_id      INTEGER PRIMARY KEY AUTOINCREMENT,
  interaction_id   TEXT NOT NULL REFERENCES fct_interaction (interaction_id),
  field_name       TEXT NOT NULL,
  rule_id          TEXT NOT NULL REFERENCES dim_rule (rule_id),
  sentence_no      INTEGER NOT NULL,
  matched_text     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_fct_interaction_date
  ON fct_interaction (interaction_date);

CREATE INDEX IF NOT EXISTS idx_fct_interaction_pain
  ON fct_interaction (primary_pain_point);

CREATE INDEX IF NOT EXISTS idx_evidence_interaction
  ON fct_extraction_evidence (interaction_id);
