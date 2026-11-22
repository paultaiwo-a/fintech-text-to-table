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

Flow diagram: `docs/architecture.md`. Scoring: `docs/scoring.md`. Columns: `docs/data_dictionary.md`.

### How to run (from this repo)

```bash
git clone https://github.com/paultaiwo-a/fintech-text-to-table.git
cd fintech-text-to-table

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Get a CSV that includes **Consumer complaint narrative** (Narratives Archive Full Records, or your own filtered export with that column).

**Option A — default path**

```bash
mkdir -p data/raw
cp /path/to/your-export.csv data/raw/complaints.csv
python -m src.build
```

**Option B — another file (no copy needed)**

```bash
python -m src.build --csv /path/to/another-cfpb-export.csv
```

You can point `--csv` at any compatible export. Ingest still filters by the products in `config/scoring.yaml` and caps rows at `ingest.max_rows`. Change those settings if you want different products or a higher cap.

That rebuilds `db/signals.db`, writes `exports/fct_interaction.csv`, and saves charts under `reports/figures/`.

Optional walkthrough after a successful build: `notebooks/demo.ipynb`.

CSV export always runs. Parquet is written only if `pyarrow` is installed.
