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
├── docker-compose.yml    # Local MySQL, Redis, and API services
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
| Semantic search | Complete |
| Listing signal extraction | Complete |
| Intent classification | Complete |
| Listing summarization | Complete |
| Fair Housing compliance checker | Complete |
| FastAPI service | Complete |
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
docker compose up -d mysql redis
docker compose ps
```

The MySQL container initializes the `real_estate` database and runs SQL files from `data/raw/` on first startup. Redis provides API caching and shared rate limiting.

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
python scripts/generate_semantic_sample.py
python scripts/build_semantic_index.py --source sample_10k --local-files-only
python scripts/build_semantic_index.py --source full --local-files-only
python scripts/extract_listing_signals.py --input-csv data/processed/listing_semantic_sample_10k.csv
python scripts/extract_listing_signals.py
python scripts/select_listing_signal_eval_sample.py
python scripts/build_listing_signal_eval_labels.py
python scripts/evaluate_listing_signals.py
python scripts/evaluate_entities.py --match-mode strict --error-limit 20
python scripts/evaluate_query_parser.py --include-soft-signals --error-limit 20
python scripts/train_query_intent_classifier.py
python scripts/evaluate_query_intent_classifier.py --split dev --output data/processed/query_intent_dev_results.json
python scripts/evaluate_query_intent_classifier.py
python scripts/generate_listing_summaries.py
python scripts/select_listing_summary_eval_sample.py
python scripts/build_listing_summary_eval_labels.py
python scripts/evaluate_listing_summaries.py --split dev --output data/processed/listing_summary_dev_results.json
python scripts/evaluate_listing_summaries.py
python scripts/prepare_listing_summary_self_review.py
python scripts/build_compliance_eval_labels.py
# After manually reviewing the local MLS-neutral candidates:
python scripts/build_compliance_eval_labels.py --mark-mls-reviewed
python scripts/evaluate_compliance_checker.py
python scripts/check_listing_compliance.py --input-csv data/processed/listing_semantic_sample_10k.csv
```

The workflow currently extracts listing samples, builds taxonomy seed terms, converts the curated taxonomy to JSON, generates cleaned listing remarks, generates a reusable city list, builds local semantic-search indexes, extracts listing-level signals, evaluates the Week 3 entity extractor and Week 4 query parser, trains a language-based search-intent classifier, and generates and evaluates listing summaries.

## API

Build an active pass-only search snapshot before starting the API. The snapshot and trained intent model remain local under `data/models/` and are mounted read-only in the container.

Run the complete local stack:

```bash
docker compose up --build
```

For code iteration, start MySQL and Redis in Docker, then run the API from the Conda environment:

```bash
docker compose up -d mysql redis
uvicorn src.real_estate_nlp.api.app:app --reload
```

Open `http://127.0.0.1:8000/docs` for interactive OpenAPI documentation. `GET /health` reports process liveness; `GET /ready` succeeds only after the active snapshot, intent model, dense model, and Cross Encoder have been loaded. The public endpoints are `/search`, `/parse-query`, `/extract-entities`, `/summarize`, `/check-compliance`, and `/classify-intent`. `/search` defaults to `search_profile: "quality"` for Hybrid RRF plus Cross Encoder reranking; use `"fast"` for Hybrid RRF only.

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
pytest tests/test_week5.py
pytest tests/test_week6.py
pytest tests/test_week7.py
pytest tests/test_week8.py
pytest tests/test_week9.py
pytest tests/test_api.py
```

Current tests cover setup, taxonomy assets, sample queries, listing sample quality, text cleaning edge cases, entity extraction behavior, query parsing, schema validation, SQL generation, SQL injection protection, semantic-search components, listing-level signal extraction, query-intent classification, listing summarization, answerability checks, Fair Housing compliance rules, and API contracts, caching, rate limiting, and readiness behavior.

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

- `data/processed/listing_semantic_sample_10k.csv`
  - Local fixed 10k sample for Week 5 semantic search and latency review.
  - Ignored by Git as generated data.

- `src/real_estate_nlp/text_cleaner.py`
  - Text normalization pipeline for MLS listing remarks.

- `scripts/generate_cleaned_dataset.py`
  - Generates the cleaned listing sample.

- `scripts/generate_city_list.py`
  - Generates `data/processed/valid_cities.json` from the local MySQL database.

- `scripts/generate_semantic_sample.py`
  - Generates the fixed 10k listing sample for semantic-search experiments.

- `scripts/build_semantic_index.py`
  - Builds local FAISS indexes for the 10k sample or full `rets_property` remarks.

- `src/real_estate_nlp/semantic_search.py`
  - Embedding-based listing retrieval with configurable sentence-transformers model, FAISS indexing, save/load support, and candidate reranking.

- `src/real_estate_nlp/keyword_search.py`
  - BM25 keyword-search baseline for Week 5 comparison.

- `src/real_estate_nlp/entity_extractor.py`
  - Rule-based entity extractor for listing remarks.
  - Extracts numeric facts, taxonomy terms, amenities, rooms, property features, location signals, and transaction terms.

- `src/real_estate_nlp/signal_extractor.py`
  - Converts full listing records into listing-level signals for search, filtering, indexing, and ranking.

- `scripts/extract_listing_signals.py`
  - Generates compact listing-level JSONL signals from MySQL or a local CSV input.
  - The full-table run writes `listing_signals.jsonl`; a CSV input can be used for smaller local runs.

- `scripts/evaluate_listing_signals.py`
  - Evaluates structured numeric fields, remark-derived numeric fallbacks, and text signals against the local Week 6 gold labels.

- `data/processed/listing_signal_eval_labels.json`
  - Local reviewed evaluation set of 200 real listings for Week 6 signal extraction.
  - Ignored by Git with the source records and evaluation results.

- `data/processed/listing_signals.jsonl`
  - Local generated Week 6 listing-signal output for the full `rets_property` table.
  - Current full run contains 53,122 records.
  - Ignored by Git as generated data.

- `src/real_estate_nlp/listing_summarizer.py`
  - Builds two-sentence listing summaries from trusted MLS facts and compact text signals.
  - Keeps an extractive sentence-selection method for remarks-only use cases.

- `src/real_estate_nlp/answerability_checker.py`
  - Explains whether a request can be handled by the current listing-search workflow before and after query execution.

- `src/real_estate_nlp/compliance_checker.py`
  - Screens listing remarks against the versioned Federal Fair Housing rule set and returns publication status with precise evidence spans.

- `src/real_estate_nlp/compliance_rules.py`
  - Defines the auditable `federal-1.1` policy rules, protected classes, risk types, and severity levels.

- `scripts/build_compliance_eval_labels.py`
  - Builds a local 264-item evaluation set with synthetic policy examples and manually reviewed neutral MLS remarks.

- `scripts/evaluate_compliance_checker.py`
  - Reports known-violation recall, actionable-alert precision, status accuracy, false-positive rate, and protected-class recall.

- `scripts/check_listing_compliance.py`
  - Applies the checker to a local CSV and writes per-listing JSONL review results.

- `scripts/generate_listing_summaries.py`
  - Generates a local JSONL summary artifact for the full `rets_property` table.

- `scripts/evaluate_listing_summaries.py`
  - Calculates ROUGE-L and combined fact coverage against the local evaluation labels.

- `data/processed/listing_summaries.jsonl`
  - Local full-table Week 8 summary output with 53,122 records.
  - Ignored by Git with evaluation samples, reference summaries, and review sheets.

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

- `src/real_estate_nlp/query_intent_classifier.py`
  - Classifies search-query language as browsing, researching, or high-intent inquiry.
  - Replaces known city names with a shared token before vectorization to prevent location-label shortcuts.
  - Uses calibrated logistic-regression probabilities and exposes an uncertainty flag.

- `scripts/train_query_intent_classifier.py`
  - Trains the Week 7 classifier from the curated query-intent labels.

- `scripts/evaluate_query_intent_classifier.py`
  - Evaluates the saved classifier on the fixed held-out split and writes local metrics.

- `data/processed/query_intent_labels.json`
  - Curated Week 7 dataset with 504 manually authored real-estate queries.
  - Contains 360 training queries, 72 development queries, and 72 independent final-test queries.
  - Versioned because it is a reusable, non-sensitive training and evaluation asset.

- `data/processed/entity_eval_labels.json`
  - Local reviewed evaluation set with 200 listing remarks and 2,619 labeled entities.

- `data/models/entity_ner/`
  - Local saved spaCy NER experiment model.

- `data/models/semantic/`
  - Local FAISS indexes, embeddings, and metadata for semantic search.
  - Ignored by Git as generated model artifacts.

- `data/models/query_intent/`
  - Local saved classifier and metadata for Week 7 intent inference.
  - Ignored by Git as generated model artifacts.

- `notebooks/01_remark_exploration.ipynb`
  - Week 1 listing, taxonomy, and query exploration.

- `notebooks/02_text_cleaning_exploration.ipynb`
  - Week 2 raw-vs-cleaned text profiling and before/after review.

- `notebooks/03_entity_extraction_evaluation.ipynb`
  - Week 3 rule, NER, and hybrid extraction comparison with error analysis.

- `notebooks/04_query_parser_evaluation.ipynb`
  - Week 4 parser output review, hard/soft filter evaluation, SQL generation examples, and validation checks.

- `notebooks/05_semantic_search_evaluation.ipynb`
  - Week 5 MiniLM, MPNet, and BM25 comparison with latency checks and graded proxy relevance metrics.

- `notebooks/06_listing_signal_extraction.ipynb`
  - Week 6 signal schema review, coverage profile, common signal values, examples, and light error analysis.

- `notebooks/07_query_intent_classification.ipynb`
  - Week 7 label review, held-out metrics, confidence analysis, error examples, and parser integration output.

- `notebooks/08_listing_summarization.ipynb`
  - Week 8 evaluation-sample profile, summary quality checks, automatic metrics, examples, self-review sheet preview, and AnswerabilityChecker cases.

- `notebooks/09_fair_housing_compliance.ipynb`
  - Week 9 label profile, compliance metrics, protected-class recall, and local error review.

- `docs/week1_report.md`
  - Week 1 summary and validation notes.

- `docs/week2_report.md`
  - Week 2 summary and validation notes.

- `docs/week3_report.md`
  - Week 3 entity extraction summary and validation notes.

- `docs/week4_report.md`
  - Week 4 query parser summary and validation notes.

- `docs/week5_report.md`
  - Week 5 semantic search summary, model comparison, latency notes, and validation results.

- `docs/week6_report.md`
  - Week 6 listing signal extraction summary, schema notes, coverage checks, and validation results.

- `docs/week7_report.md`
  - Week 7 query-intent classification summary, held-out evaluation, and integration notes.

- `docs/week8_report.md`
  - Week 8 listing summarization summary, evaluation results, and answerability-layer notes.

- `docs/week9_report.md`
  - Week 9 Fair Housing compliance summary, local evaluation results, and validation notes.

- `docs/fair_housing_rules.md`
  - Federal Fair Housing screening scope, review outcomes, integration example, and policy-maintenance guidance.

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

Current semantic search results on the fixed 10k listing sample:

| Method | Precision@5 | NDCG@5 | MRR |
| --- | ---: | ---: | ---: |
| BM25 | 0.82 | 0.858 | 0.90 |
| MPNet | 0.84 | 0.781 | 0.90 |
| MiniLM | 0.82 | 0.730 | 0.90 |

Current listing signal quality on the reviewed Week 6 evaluation set:

| Metric | Value |
| --- | ---: |
| Structured field accuracy | 1.000 |
| Free-text F1 | 0.799 |
| Keyword integrity | 1.000 |

Current listing signal coverage on the full `rets_property` output (53,122 records):

| Signal bucket | Coverage |
| --- | ---: |
| Interior features | 83.9% |
| Exterior features | 78.4% |
| Location features | 76.0% |
| Rooms | 71.5% |
| Condition | 66.7% |
| Amenities | 56.6% |
| Parking | 49.4% |
| Investment features | 17.3% |
| Financing terms | 2.8% |

Current language-intent classification results on the independent Week 7 final-test query set:

| Metric | Value |
| --- | ---: |
| Held-out queries | 72 |
| Accuracy | 0.958 |
| Browsing F1 | 0.933 |
| Researching F1 | 1.000 |
| High-intent inquiry F1 | 0.941 |

Current listing summarization results on the independent Week 8 final-test set:

| Metric | Value |
| --- | ---: |
| Held-out listings | 30 |
| ROUGE-L | 0.457 |
| Fact coverage | 0.733 |

These results use source-based labels with independently written reference summaries and `feature_gold` terms aligned to the original listing remark.

Current Fair Housing compliance results on the local Week 9 evaluation set:

| Metric | Value |
| --- | ---: |
| Evaluation items | 264 |
| Known-violation recall | 1.000 |
| Actionable-alert precision | 1.000 |
| Status accuracy | 1.000 |
| Clean-listing false-positive rate | 0.000 |

The local evaluation set contains 204 synthetic policy examples and 60 manually reviewed neutral MLS remarks. The synthetic examples cover explicit violations, review-sensitive wording, paraphrases, longer contexts, multiple signals, and neutral counterexamples. The `federal-1.1` rules close the identified coverage and boundary gaps on this frozen local set. It remains ignored because it includes local MLS text.

## Final Deliverables

- Complete Python codebase
- Setup and usage documentation
- API documentation
- Data schema notes
- Test coverage report
- Demo interface
- Final technical report with metrics and analysis
- Presentation materials
