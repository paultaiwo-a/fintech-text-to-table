# fintech-text-to-table

Turn unstructured financial complaint text into a typed, analytics-ready table — then answer which pain points drive switching and which interactions are the strongest acquisition signals.

**Stack:** Python (pandas), SQLite + SQL, matplotlib, light plotly. Rule-based extractors with an evidence audit trail.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Download the CFPB Consumer Complaint Database CSV and place it at:
#   data/raw/complaints.csv
# https://www.consumerfinance.gov/data-research/consumer-complaints/

python -m src.build
python -m src.insights
```

Optional live walkthrough: open `notebooks/demo.ipynb` and Run All.

## Project layout

See `docs/` after the schema and scoring docs land. Pipeline code lives in `src/`; analysis SQL in `sql/analysis/`.
