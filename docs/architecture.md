### Architecture

One command runs the pipeline end to end: `python -m src.build`.

```text
CFPB CSV                    config/
(data/raw/complaints.csv)   scoring.yaml + lexicons
        |                            |
        v                            v
   pipeline/ingest.py  -->  raw_complaints
        |
   pipeline/clean.py   -->  stg_sentences
        |
   pipeline/extract.py -->  fields + evidence
        |
   pipeline/score.py   -->  sentiment / severity / lead signal
        |
   pipeline/load.py    -->  fct_interaction
                           fct_interaction_pain_point
                           fct_extraction_evidence
                           dim_pain_point / dim_rule
        |
   pipeline/quality.py -->  pass / fail checks
        |
   insights.py         --> charts (output/figures/)
                           export (output/exports/)
```



### What each step does


| Step     | Module                     | Output                                           |
| -------- | -------------------------- | ------------------------------------------------ |
| Ingest   | `src/pipeline/ingest.py`   | `raw_complaints`                                 |
| Clean    | `src/pipeline/clean.py`    | `stg_sentences`                                  |
| Extract  | `src/pipeline/extract.py`  | pain point, switching, amounts, delays, evidence |
| Score    | `src/pipeline/score.py`    | sentiment, frustration, severity, lead signal    |
| Load     | `src/pipeline/load.py`     | fact + dim tables in `output/signals.db`         |
| Quality  | `src/pipeline/quality.py`  | row checks after load                            |
| Insights | `src/insights.py`          | SQL charts + CSV export                          |




### Tables people query

```text
dim_pain_point ──┐
                 ├── fct_interaction_pain_point
fct_interaction ─┤
                 └── fct_extraction_evidence
dim_rule ─────────── fct_extraction_evidence
```

`fct_interaction` is the main table (one row per complaint). Evidence rows show which rule and sentence produced a value.
