### Architecture

One command runs the pipeline end to end: `python -m src.build`.

```text
CFPB CSV                    config/
(data/raw/complaints.csv)   scoring.yaml + lexicons
        |                            |
        v                            v
   ingest.py  -->  raw_complaints
        |
   clean.py   -->  stg_sentences
        |
   extract.py -->  fields + evidence
        |
   score.py   -->  sentiment / severity / lead signal
        |
   load.py    -->  fct_interaction
                   fct_interaction_pain_point
                   fct_extraction_evidence
                   dim_pain_point / dim_rule
        |
   quality.py -->  pass / fail checks
        |
   insights.py --> charts (reports/figures/)
                   export (exports/fct_interaction.csv)
```

```mermaid
flowchart LR
  A[complaints.csv] --> B[ingest]
  B --> C[clean]
  C --> D[extract]
  D --> E[score]
  E --> F[load SQLite]
  F --> G[quality checks]
  G --> H[insights + export]
```

### What each step does

| Step | Module | Output |
| --- | --- | --- |
| Ingest | `src/ingest.py` | `raw_complaints` |
| Clean | `src/clean.py` | `stg_sentences` |
| Extract | `src/extract.py` | pain point, switching, amounts, delays, evidence |
| Score | `src/score.py` | sentiment, frustration, severity, lead signal |
| Load | `src/load.py` | fact + dim tables in `db/signals.db` |
| Quality | `src/quality.py` | row checks after load |
| Insights | `src/insights.py` | SQL charts + CSV export |

### Tables people query

```text
dim_pain_point ──┐
                 ├── fct_interaction_pain_point
fct_interaction ─┤
                 └── fct_extraction_evidence
dim_rule ─────────── fct_extraction_evidence
```

`fct_interaction` is the main table (one row per complaint). Evidence rows show which rule and sentence produced a value.
