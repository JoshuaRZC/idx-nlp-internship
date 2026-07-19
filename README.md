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
| Entity extraction | Complete |
| Query parsing to SQL filters | Complete |
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
python scripts/generate_city_list.py
python scripts/evaluate_entities.py --match-mode strict --error-limit 20
python scripts/evaluate_query_parser.py --include-soft-signals --error-limit 20
```

The workflow currently extracts a listing sample, builds taxonomy seed terms, converts the curated taxonomy to JSON, generates cleaned listing remarks, generates a reusable city list, evaluates the Week 3 entity extractor, and evaluates the Week 4 query parser.

## Testing

Run the full test suite with:

```bash
pytest
```

Run weekly validation tests directly:

```bash
pytest tests/test_week1.py
pytest tests/test_week2.py
pytest tests/test_week3.py
pytest tests/test_week4.py
```

Current tests cover setup, taxonomy assets, sample queries, listing sample quality, text cleaning edge cases, entity extraction behavior, query parsing, schema validation, SQL generation, and SQL injection protection.

## Current Artifacts

- `data/processed/taxonomy.json`
  - Curated real estate taxonomy for listing remarks and search queries.

- `data/processed/sample_queries.json`
  - Labeled search-query examples with intent, entities, and difficulty.

- `data/processed/valid_cities.json`
  - City list generated from `rets_property.L_City`.
  - Used by the query parser and schema validator.

- `data/processed/listing_sample_cleaned.csv`
  - Local generated dataset with original `remarks` and `remarks_cleaned`.
  - Ignored by Git as generated data.

- `scripts/text_cleaning.py`
  - Text normalization pipeline for MLS listing remarks.

- `scripts/generate_cleaned_dataset.py`
  - Generates the cleaned listing sample.

- `scripts/generate_city_list.py`
  - Generates `data/processed/valid_cities.json` from the local MySQL database.

- `scripts/entity_extractor.py`
  - Rule-based entity extractor for listing remarks.
  - Extracts numeric facts, taxonomy terms, amenities, rooms, property features, location signals, and transaction terms.

- `scripts/evaluate_entities.py`
  - Evaluates entity predictions with precision, recall, and F1.
  - Supports strict, overlap, value, and span-style matching.

- `scripts/train_ner.py`
  - Trains the optional spaCy NER experiment model.

- `src/real_estate_nlp/query_parser.py`
  - Parses natural-language search queries into hard SQL filters and soft search signals.
  - Generates parameterized SQL clauses for database-backed filters.

- `src/real_estate_nlp/schema_validator.py`
  - Validates parser output before SQL generation or downstream use.

- `scripts/evaluate_query_parser.py`
  - Evaluates query parser output against the labeled Week 1 search-query set.

- `data/processed/entity_eval_labels.json`
  - Local reviewed evaluation set with 200 listing remarks and 2,619 labeled entities.

- `data/models/entity_ner/`
  - Local saved spaCy NER experiment model.

- `notebooks/01_remark_exploration.ipynb`
  - Week 1 listing, taxonomy, and query exploration.

- `notebooks/02_text_cleaning_exploration.ipynb`
  - Week 2 raw-vs-cleaned text profiling and before/after review.

- `notebooks/03_entity_extraction_evaluation.ipynb`
  - Week 3 rule, NER, and hybrid extraction comparison with error analysis.

- `notebooks/04_query_parser_evaluation.ipynb`
  - Week 4 parser output review, hard/soft filter evaluation, SQL generation examples, and validation checks.

- `docs/week1_report.md`
  - Week 1 summary and validation notes.

- `docs/week2_report.md`
  - Week 2 summary and validation notes.

- `docs/week3_report.md`
  - Week 3 entity extraction summary and validation notes.

- `docs/week4_report.md`
  - Week 4 query parser summary and validation notes.

## Evaluation

Current entity extraction results on the reviewed held-out evaluation set:

| System | Match mode | Precision | Recall | F1 |
| --- | --- | ---: | ---: | ---: |
| Rule extractor | Strict | 0.889 | 0.814 | 0.850 |
| Rule extractor | Overlap | 0.916 | 0.839 | 0.876 |
| Rule extractor | Value | 0.925 | 0.848 | 0.885 |
| spaCy NER experiment | Span | 0.822 | 0.727 | 0.772 |
| Hybrid extractor | Span | 0.877 | 0.831 | 0.853 |

Current query parser results on the 120 labeled Week 1 sample queries:

| Metric | Value |
| --- | ---: |
| Hard-filter exact match rate | 1.000 |
| Soft-signal exact match rate | 1.000 |
| Full-filter exact match rate | 0.917 |
| Expected fields matched | 205 / 205 |

## Final Deliverables

- Complete Python codebase
- Setup and usage documentation
- API documentation
- Data schema notes
- Test coverage report
- Demo interface
- Final technical report with metrics and analysis
- Presentation materials
