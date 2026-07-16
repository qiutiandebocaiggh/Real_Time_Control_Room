# Real-Time Operations Control Room

A real-time data engineering and operational monitoring application built with **Python, Flask, SQLAlchemy, PostgreSQL, and Chart.js**.

The system receives newline-delimited JSON events over TCP, validates and enriches them, rejects duplicate or invalid records, persists accepted events, exposes operational APIs, and refreshes a browser dashboard every two seconds.

This portfolio project demonstrates an end-to-end workflow covering stream ingestion, data modelling, data-quality controls, process separation, operational state management, API development, and live visualisation.

![real-time-control-room](/Users/apple/Desktop)

## Architecture

```text
Synthetic event simulator
        │
        │ TCP / NDJSON :1337
        ▼
Independent ingestion worker
        │
        │ validation · enrichment · deduplication · reconnect
        ▼
PostgreSQL :5433
        │
        │ SQLAlchemy models and queries
        ▼
Flask API :5001
        │
        ▼
Chart.js operations dashboard
```

The web application and ingestion worker run as separate processes. A source-stream interruption therefore does not require the dashboard service to restart.

## Key capabilities

- Configurable synthetic trade and price event generator
- TCP ingestion of newline-delimited JSON messages
- Automatic source reconnection after stream interruption
- Structural and business-rule validation before persistence
- Trade deduplication through unique trade identifiers
- Instrument-reference enrichment for API and dashboard output
- Persistent ingestion counters and connection status
- PostgreSQL-backed trade, price, instrument, and operational-state models
- Flask REST endpoints for health, instruments, latest events, and cash flow
- Auto-refreshing browser dashboard with independent API error handling
- Raw event retention for traceability and debugging

## Technology stack

| Layer | Technology |
|---|---|
| Language | Python 3.11+ |
| Web/API | Flask |
| ORM | Flask-SQLAlchemy / SQLAlchemy |
| Database | PostgreSQL |
| Stream transport | TCP sockets with NDJSON messages |
| Front end | HTML, JavaScript, Chart.js |
| Configuration | `python-dotenv` |
| Code quality | Ruff |
| Local infrastructure | Docker for PostgreSQL |

## Data flow

1. The simulator loads a synthetic instrument universe from `simulator/instruments.csv`.
2. It generates price and trade events and publishes each event as one JSON line over TCP.
3. The ingestion worker connects to the stream and continuously reads incoming messages.
4. Each message is parsed, validated, and matched to reference instrument data.
5. Duplicate trades are counted but not inserted again.
6. Accepted events and ingestion status are committed to PostgreSQL.
7. Flask endpoints query the persisted data and return enriched JSON responses.
8. The dashboard refreshes the cash-flow chart and latest-event tables at a configurable interval.

## Event examples

### Trade event

```json
{
  "type": "trade",
  "data": {
    "trade_id": "8fc14a72-c86a-4ac4-a9ec-e5528fd12f36",
    "instrument_id": "inst-003",
    "price": 120.1158,
    "volume": 9138,
    "side": "SELL",
    "currency": "EUR",
    "date": "2026-07-16T16:04:51.758299+00:00"
  }
}
```

### Price event

```json
{
  "type": "price",
  "data": {
    "instrument_id": "inst-001",
    "price": 51.2847,
    "date": "2026-07-16T16:04:52.102304+00:00"
  }
}
```

## Data-quality controls

Incoming events are rejected and counted when they violate the expected contract. Current checks include:

- valid JSON and object structure
- supported `trade` or `price` event type
- required non-empty identifiers and currencies
- positive prices and volumes
- integer trade volume
- `BUY` or `SELL` trade side
- timezone-aware ISO-8601 timestamp
- known reference instrument
- trade currency matching the instrument currency
- duplicate `trade_id` detection

The `ingestion_status` table records processed trades, processed prices, duplicate trades, invalid messages, connection state, the latest event time, and the latest error.

## Metric definition

For each trade:

```text
notional = price × volume
```

Signed notional is calculated as:

```text
BUY  → -notional
SELL → +notional
```

The dashboard displays cumulative signed notional for EUR-denominated trades. This is an **operational cash-flow indicator**, not accounting profit and loss. It does not include positions, mark-to-market valuation, realised/unrealised P&L, or foreign-exchange conversion.

## Quick start

### Prerequisites

- Python 3.11 or later
- Docker
- Local ports `1337`, `5001`, and `5433` available

### 1. Clone and install

```bash
git clone https://github.com/qiutiandebocaiggh/Real_Time_Control_Room.git
cd Real_Time_Control_Room

python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -e ".[dev]"

cp .env.example .env
```

On Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

### 2. Start PostgreSQL

```bash
docker run \
  --name control-room-postgres \
  -e POSTGRES_USER=control_room \
  -e POSTGRES_PASSWORD=control_room \
  -e POSTGRES_DB=control_room \
  -p 5433:5432 \
  -d postgres:16
```

For an existing stopped container:

```bash
docker start control-room-postgres
```

Confirm database readiness:

```bash
docker exec control-room-postgres \
  pg_isready \
  -U control_room \
  -d control_room
```

### 3. Start the simulator

Open the first terminal:

```bash
source .venv/bin/activate

python simulator/stream_generator.py \
  --duplicate-rate 0.03 \
  --interval-min 0.5 \
  --interval-max 1.2
```

### 4. Start the ingestion worker

Open the second terminal:

```bash
source .venv/bin/activate
python ingest.py
```

### 5. Start the Flask application

Open the third terminal:

```bash
source .venv/bin/activate
python run.py
```

Open the dashboard at:

```text
http://127.0.0.1:5001
```

The application creates the database tables when needed and loads the synthetic instrument reference data during startup.

## Configuration

Runtime values are read from `.env`. The committed `.env.example` contains the local defaults:

```dotenv
FLASK_HOST=0.0.0.0
FLASK_PORT=5001
DATABASE_URL=postgresql+psycopg2://control_room:control_room@localhost:5433/control_room
STREAM_HOST=127.0.0.1
STREAM_PORT=1337
STREAM_RECONNECT_SECONDS=3
INSTRUMENT_FILE=simulator/instruments.csv
DASHBOARD_REFRESH_MS=2000
DATA_FRESHNESS_THRESHOLD_SECONDS=10
```

Do not commit the local `.env` file.

## API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/` | Render the operations dashboard |
| `GET` | `/api/health` | Return database counts and ingestion status |
| `GET` | `/api/instruments` | Return instrument reference data |
| `GET` | `/api/trades/latest?limit=20` | Return the latest enriched trades |
| `GET` | `/api/prices/latest?limit=20` | Return the latest enriched prices |
| `GET` | `/api/cash-flow?currency=EUR` | Return cumulative signed notional by currency |

Example health check:

```bash
curl -sS http://127.0.0.1:5001/api/health \
  | python -m json.tool
```

Example latest trades request:

```bash
curl -sS \
  "http://127.0.0.1:5001/api/trades/latest?limit=2" \
  | python -m json.tool
```

## Database model

| Table | Purpose |
|---|---|
| `instruments` | Instrument names, country, sector, exchange, type, and currency |
| `trades` | Validated trade events with calculated notional and signed notional |
| `prices` | Validated market-price events |
| `ingestion_status` | Connection status, counters, timestamps, and latest error |

Trade and price records reference the `instruments` table through foreign keys. API responses expose both the raw instrument identifier and enriched business attributes.

## Reliability behaviour

### Duplicate handling

`trade_id` is the primary key of the trade table. The worker checks for an existing record before insertion and also handles a database integrity error. Duplicate events increase `duplicate_trade_count` without increasing the stored-trade count.

### Stream reconnection

When the TCP source closes or becomes unavailable, the worker:

1. persists `disconnected` status
2. records the latest connection error
3. waits for the configured retry interval
4. reconnects automatically
5. resumes ingestion without restarting Flask

### Traceability

Accepted trade and price records retain the original JSON line in `raw_json`, allowing the stored representation to be compared with the source event during debugging or reconciliation.

## Validation and smoke tests

Run static checks:

```bash
python -m ruff check app run.py ingest.py simulator
python -m compileall -q app run.py ingest.py simulator
git diff --check
```

Check database and ingestion-counter consistency while the system is running:

```bash
docker exec control-room-postgres \
  psql \
  -U control_room \
  -d control_room \
  -c "
  SELECT
      (SELECT COUNT(*) FROM trades) AS stored_trades,
      processed_trade_count,
      (SELECT COUNT(*) FROM prices) AS stored_prices,
      processed_price_count,
      duplicate_trade_count,
      invalid_message_count
  FROM ingestion_status
  WHERE id = 1;
  "
```

Expected invariants:

```text
stored_trades = processed_trade_count
stored_prices = processed_price_count
```

## Project structure

```text
.
├── app/
│   ├── __init__.py              # Flask application factory
│   ├── config.py                # Environment-based configuration
│   ├── extensions.py            # SQLAlchemy extension
│   ├── ingestion.py             # Validation and TCP ingestion logic
│   ├── models.py                # Database models and serializers
│   ├── routes.py                # Dashboard and REST endpoints
│   ├── services.py              # Reference-data and status services
│   └── templates/
│       └── dashboard.html       # Chart.js dashboard
├── simulator/
│   ├── instruments.csv          # Synthetic reference dataset
│   └── stream_generator.py      # Synthetic TCP event source
├── ingest.py                    # Ingestion-worker entry point
├── run.py                       # Flask entry point
├── pyproject.toml               # Dependencies and Ruff configuration
└── .env.example                 # Local configuration template
```

## Engineering decisions

- **Separate web and ingestion processes:** isolates dashboard availability from source-stream failures.
- **PostgreSQL instead of in-memory state:** preserves events and operational counters across process restarts.
- **Reference-data foreign keys:** reject unknown instruments and support enriched downstream output.
- **Unique trade identifiers:** provide idempotent duplicate handling.
- **Application factory pattern:** keeps configuration and extension initialisation modular.
- **Synthetic public data source:** makes the project reproducible without proprietary binaries or external credentials.
- **Simple local architecture:** prioritises a clear, inspectable end-to-end implementation over unnecessary distributed components.

## Design trade-offs and next steps

The current implementation is intentionally small and locally reproducible. The main production-oriented extensions would be:

- Docker Compose for all four services
- Alembic database migrations
- Pytest unit and integration coverage with GitHub Actions
- batched writes and retry handling for transient database failures
- fixed-precision monetary columns
- authentication, TLS, and production WSGI deployment
- dashboard freshness, duplicate-rate, and exception KPI cards

## Data and repository note

All instruments, prices, and trades in this repository are synthetic. The event simulator and reference dataset were created for this public portfolio project; no proprietary market generator or confidential source data is included.

---

Portfolio project by **Ray Sun**.
