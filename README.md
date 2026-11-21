### Fintech text to table

##### Paul Taiwo-Adeyemo

CFPB complaint narratives turned into one table you can query. Each row is an interaction with a pain point, switching flag, dollar amount, delay, severity, and a lead-signal score. The rules that fired are stored so you can see where a value came from.

The question is which pain points make people want to switch, and which rows look like the strongest acquisition signals.

Data: [CFPB Consumer Complaint Database](https://www.consumerfinance.gov/data-research/consumer-complaints/). Put the CSV at `data/raw/complaints.csv`.

Scoring is in `docs/scoring.md`. Column list is in `docs/data_dictionary.md`. Charts land in `reports/figures/`.

### How to Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python -m src.build
```

`python -m src.build` loads the CSV, cleans the text, extracts the fields, scores the rows, writes SQLite, runs the quality checks, and saves the charts.

Optional walkthrough: `notebooks/demo.ipynb`.
