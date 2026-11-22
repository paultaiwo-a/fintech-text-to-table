### Fintech text to table

##### Paul Taiwo-Adeyemo

CFPB complaint narratives turned into one table you can query. Each row is an interaction with a pain point, switching flag, dollar amount, delay, severity, and a lead-signal score. The rules that fired are stored so you can see where a value came from.

The question is which pain points make people want to switch, and which rows look like the strongest acquisition signals.

### Data

As of September 2026, the live [Consumer Complaint Database](https://www.consumerfinance.gov/data-research/consumer-complaints/) no longer ships complaint narratives ([release notes](https://cfpb.github.io/api/ccdb/release-notes.html)). Narratives come from the [CFPB Narratives Archive](https://www.consumerfinance.gov/foia-requests/foia-electronic-reading-room/cfpb-consumer-complaint-database-narratives-archive/).

**Source files used here (Full Records):**

- CCDB Export January 2026 through February 2026
- CCDB Export March 2026
- CCDB Export April 2026

**Filters applied for this project:**

- Date received: **2026-01-01 to 2026-04-30**
- Checking or savings account → Checking account, Savings account
- Credit card → General-purpose credit card or charge card
- Money transfer, virtual currency, or money service → Mobile or digital wallet; Domestic (US) money transfer; International money transfer; Money order, traveler's check or cashier's check; Check cashing service
- Non-empty **Consumer complaint narrative** only

The filtered working file is **27,991** rows. Raw data is not in git (`data/raw/` is ignored). Pipeline cap is 100,000 (`config/scoring.yaml` → `ingest.max_rows`).

Flow diagram: `docs/architecture.md`. Run guide (default or another CFPB file): `docs/how_to_run.md`. Scoring: `docs/scoring.md`. Columns: `docs/data_dictionary.md`.

### How to run

Full steps (clone, data, default CSV, or `--csv` for another file): **`docs/how_to_run.md`**.

Short version:

```bash
git clone https://github.com/paultaiwo-a/fintech-text-to-table.git
cd fintech-text-to-table
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# default path
mkdir -p data/raw
cp /path/to/your-export.csv data/raw/complaints.csv
python -m src.build

# or another file
python -m src.build --csv /path/to/another-export.csv
```

Outputs: `db/signals.db`, `exports/fct_interaction.csv`, `reports/figures/`. Optional: `notebooks/demo.ipynb`.
