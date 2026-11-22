### How to run

#### Setup (once)

```bash
git clone https://github.com/paultaiwo-a/fintech-text-to-table.git
cd fintech-text-to-table

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

#### Data you need

A CSV with at least:

- `Complaint ID`
- `Date received`
- `Product`
- `Sub-product`
- `Issue`
- `Sub-issue`
- `Company`
- `State`
- `Consumer complaint narrative`

The live CFPB download often has **no narrative**. Use the [Narratives Archive](https://www.consumerfinance.gov/foia-requests/foia-electronic-reading-room/cfpb-consumer-complaint-database-narratives-archive/) Full Records exports, or any file that still has the narrative column.

#### Run with the default file

```bash
mkdir -p data/raw
cp /path/to/your-export.csv data/raw/complaints.csv
python -m src.build
```

#### Run with a different CFPB file

```bash
python -m src.build --csv /path/to/another-export.csv
```

No need to overwrite `data/raw/complaints.csv`.

#### Change products or row cap

Edit `config/scoring.yaml`:

- `ingest.products` — which CFPB products to keep
- `ingest.max_rows` — max rows loaded
- `ingest.lookback_years` — date filter from today

Then run `python -m src.build` (or `--csv ...`) again.

#### Outputs

| Path | What it is |
| --- | --- |
| `output/signals.db` | SQLite tables (`fct_interaction`, evidence, dims) |
| `output/exports/fct_interaction.csv` | Main table export |
| `output/figures/` | Charts from insights |

Optional after a successful build: open `notebooks/demo.ipynb` and Run All.

#### Flow

See `docs/architecture.md`.
