# Data dictionary

Main analyst table: **`fct_interaction`** (one row per complaint/call).

| Column | Type | Notes |
| --- | --- | --- |
| interaction_id | TEXT | `CFPB-<id>` |
| source | TEXT | `cfpb_complaint` |
| source_record_id | TEXT | Original CFPB id |
| interaction_date | DATE | Date received |
| product | TEXT | CFPB product |
| company_size_band | TEXT | `top_10` / `next_40` / `long_tail` |
| state | TEXT | 2-letter state |
| channel_primary | TEXT | Channel mentioned most |
| word_count | INTEGER | Words in narrative |
| redaction_share | REAL | Share of redacted tokens |
| primary_pain_point | TEXT | Top pain-point code or `none` |
| pain_point_count | INTEGER | Distinct pain points (0–8) |
| sentiment_score | REAL | -1 to 1 |
| sentiment_label | TEXT | negative / neutral / positive |
| frustration_score | REAL | 0 to 1 |
| amount_usd_max | REAL | Largest $ mentioned |
| amount_mentions | INTEGER | Count of $ mentions |
| delay_days_max | INTEGER | Longest delay (days) |
| switching_intent | INTEGER | 0/1 |
| competitor_mentioned | INTEGER | 0/1 |
| escalation_flag | INTEGER | 0/1 |
| escalation_type | TEXT | legal / regulator / bbb / media / none |
| severity_score | INTEGER | 0–100 |
| severity_band | TEXT | low / medium / high / critical |
| lead_signal_score | INTEGER | 0–100 acquisition signal |
| needs_review | INTEGER | 0/1 |
| review_reason | TEXT | Why review was flagged |
| extractor_version | TEXT | Rule version |
| extracted_at | TIMESTAMP | Load time |

**Other tables**

| Table | Grain |
| --- | --- |
| `fct_interaction_pain_point` | interaction × pain point |
| `fct_extraction_evidence` | one row per extracted match |
| `dim_pain_point` | pain-point codes |
| `dim_rule` | extractor rules + optional precision |
| `stg_sentences` | cleaned sentences for evidence |
| `raw_complaints` | CFPB landing zone |
