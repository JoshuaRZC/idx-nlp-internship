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
| Listing sample extraction | In progress |
| Taxonomy construction | In progress |
| Text cleaning and normalization | In progress |
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

In progress.

Planned workflow:

```text
raw MLS data
  -> MySQL import
  -> sample extraction
  -> text cleaning
  -> entity and signal extraction
  -> query parsing and semantic search
  -> API and demo interface
```

## Testing

Run the full test suite with:

```bash
pytest
```

Tests will be added alongside each pipeline component.

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
