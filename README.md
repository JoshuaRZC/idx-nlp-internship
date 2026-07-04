# Real Estate Listing Intelligence System

An NLP system for turning real estate listing text into structured, searchable, and reviewable information.

The project works with MLS listing data and focuses on the language inside property descriptions: amenities, property features, search intent, buyer-facing summaries, and compliance-sensitive wording.

## Project Goals

- Normalize and clean MLS listing remarks for downstream NLP tasks
- Build a real estate terminology taxonomy from listing language
- Extract structured entities such as beds, baths, price, square footage, amenities, and location signals
- Parse natural language search queries into safe structured filters
- Support semantic search over listing remarks using embeddings and FAISS
- Classify real estate search intent from query wording
- Generate concise listing summaries for search results and alerts
- Flag Fair Housing compliance risks in listing text
- Expose the system through a FastAPI service and demo interface

## Data Sources

The project is designed around three MLS tables:

| Table | Purpose |
| --- | --- |
| `rets_property` | Active and pending listings. Primary source for listing remarks, prices, beds, baths, amenities, and location fields. |
| `rets_openhouse` | Open house schedules and related listing metadata. |
| `california_sold` | Historical sold transactions for market context and comparison. |

The main NLP field is `rets_property.L_Remarks`.

Raw MLS data is not committed to this repository. Local SQL or CSV files should be placed under `data/raw/`.

## Repository Layout

```text
.
├── data/
│   ├── raw/              # Local raw SQL/CSV files; ignored by Git
│   ├── processed/        # Derived samples, labels, taxonomy files, and cleaned outputs
│   └── models/           # Local embeddings, FAISS indexes, and trained model artifacts
├── docs/                 # Technical notes, reports, schema references, and final writeups
├── notebooks/            # Exploratory analysis and evaluation notebooks
├── scripts/              # Command-line entry points for local data and artifact tasks
├── src/
│   └── real_estate_nlp/  # Reusable project package for pipeline and API code
│       └── api/          # FastAPI application code
├── tests/                # Pytest test suite
├── docker-compose.yml    # Local MySQL service definition
├── requirements.txt      # Python dependencies
└── README.md
```

## Pipeline

| Component | Status |
| --- | --- |
| Environment setup | Complete |
| MySQL data loading | Complete |
| Listing sample extraction | Complete |
| Taxonomy construction | Complete |
| Sample query set | Complete |
| Text cleaning and normalization | Complete |
| Entity extraction | In progress |
| Query parsing to SQL filters | In progress |
| Semantic search | In progress |
| Intent classification | In progress |
| Listing summarization | In progress |
| Fair Housing compliance checker | In progress |
| FastAPI service | In progress |
| Demo interface | In progress |

## Environment Setup

Use Python 3.11 or newer.

```bash
conda create -n idx-nlp python=3.11
conda activate idx-nlp
pip install -r requirements.txt
```

## Data Setup

Raw MLS SQL files are not committed to this repository. Place the downloaded SQL files before starting MySQL:

```text
data/raw/
  rets_property.sql
  rets_openhouse.sql
  california_sold.sql
```

Start the local MySQL container and check container status:

```bash
docker compose up -d
docker compose ps
```

The MySQL container initializes the `real_estate` database and runs SQL files from `data/raw/` on first startup.

Local database connection:

```text
host: 127.0.0.1
port: 3307
user: root
password: root
database: real_estate
```

## Usage

Current local workflow:

```bash
python scripts/data_loading.py
python scripts/taxonomy_builder.py
python scripts/taxonomy_csv_to_json.py
python scripts/generate_cleaned_dataset.py
```

The workflow currently extracts a listing sample, builds taxonomy seed terms, converts the curated taxonomy to JSON, and generates cleaned listing remarks.

## Testing

Run the full test suite with:

```bash
pytest
```

Run weekly validation tests directly:

```bash
pytest tests/test_week1.py
pytest tests/test_week2.py
```

Current tests cover setup, taxonomy assets, sample queries, listing sample quality, and text cleaning edge cases.

## Current Artifacts

- `data/processed/taxonomy.json`
  - Curated real estate taxonomy for listing remarks and search queries.

- `data/processed/sample_queries.json`
  - Labeled search-query examples with intent, entities, and difficulty.

- `data/processed/listing_sample_cleaned.csv`
  - Local generated dataset with original `remarks` and `remarks_cleaned`.
  - Ignored by Git as generated data.

- `scripts/text_cleaning.py`
  - Text normalization pipeline for MLS listing remarks.

- `scripts/generate_cleaned_dataset.py`
  - Generates the cleaned listing sample.

- `notebooks/01_remark_exploration.ipynb`
  - Week 1 listing, taxonomy, and query exploration.

- `notebooks/02_text_cleaning_exploration.ipynb`
  - Week 2 raw-vs-cleaned text profiling and before/after review.

- `docs/week1_report.md`
  - Week 1 summary and validation notes.

- `docs/week2_report.md`
  - Week 2 summary and validation notes.

## Evaluation

In progress.

Planned evaluation areas:

- Taxonomy coverage over listing remarks
- Text cleaning edge-case coverage
- Entity extraction precision, recall, and F1
- Query parser accuracy on labeled search examples
- Semantic search relevance and latency
- Intent classification accuracy
- Compliance checker recall and precision

## Final Deliverables

- Complete Python codebase
- Setup and usage documentation
- API documentation
- Data schema notes
- Test coverage report
- Demo interface
- Final technical report with metrics and analysis
- Presentation materials
