### Fintech text to table

##### Paul Taiwo-Adeyemo

CFPB complaint narratives turned into one table you can query. Each row is an interaction with a pain point, switching flag, dollar amount, delay, severity, and a lead-signal score. The rules that fired are stored so you can see where a value came from.

The question is which pain points make people want to switch, and which rows look like the strongest acquisition signals.

### Data

As of September 2026, the live [Consumer Complaint Database](https://www.consumerfinance.gov/data-research/consumer-complaints/) no longer ships complaint narratives ([release notes](https://cfpb.github.io/api/ccdb/release-notes.html)). Narratives come from the [CFPB Narratives Archive](https://www.consumerfinance.gov/foia-requests/foia-electronic-reading-room/cfpb-consumer-complaint-database-narratives-archive/).

**Source files (Full Records):**

- CCDB Export January 2026 through February 2026
- CCDB Export March 2026
- CCDB Export April 2026

**Filters applied for this project:**

- Date received: **2026-01-01 to 2026-04-30**
- Checking or savings account → Checking account, Savings account
- Credit card → General-purpose credit card or charge card
- Money transfer, virtual currency, or money service → Mobile or digital wallet; Domestic (US) money transfer; International money transfer; Money order, traveler's check or cashier's check; Check cashing service
- Non-empty **Consumer complaint narrative** only

**Working file:** `data/raw/complaints.csv` — **27,991** rows (all with narratives). Pipeline cap is 100,000 (`config/scoring.yaml` → `ingest.max_rows`).

Flow diagram: `docs/architecture.md`. Scoring is in `docs/scoring.md`. Column list is in `docs/data_dictionary.md`. Charts land in `reports/figures/`.

### How to Run

Use the project venv (not system/Anaconda Python):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python -m src.build
```

`python -m src.build` loads the CSV, cleans the text, extracts the fields, scores the rows, writes SQLite, runs the quality checks, and saves the charts. CSV export always runs; parquet is written only if `pyarrow` is installed.

Optional walkthrough: `notebooks/demo.ipynb`.
