# Collector service (POC)

Collects telemetry from:
- Query Store (top queries in a time window)
- Selected DMVs (missing indexes, index usage)

Outputs into feature store tables in the target DB (or separate DB).

## Run
1) Copy `.env.example` → `.env` in repo root and fill in values.
2) Install deps (example with venv):
   - `python -m venv .venv && .venv\Scripts\activate`
   - `pip install -e services/collector`
3) Run:
   - `autotuner-collector`

## FR-01 target validation

Target metadata and connection validation are now implemented as importable services. See [Target validation](../../docs/TARGET_VALIDATION.md) for usage and backend tests. The existing collector command remains a telemetry placeholder until FR-02.

# Sprint 1 Workload Collector Foundation

Implemented first slice:

- WC-01: configure and validate a read-only SQL Server target.
- WC-02: create and track collection batches.
- Separate `AutoTunerRepository` database.

## Repository placement

Suggested repo paths:

```text
sql/
  repository/
    001_create_autotuner_repository.sql

services/
  collector/
    app.py
    config.py
    db.py
    models.py
    repository.py
    target_validator.py
    requirements.txt
    .env.example
    tests/
```

## Setup

1. Run `sql/repository/001_create_autotuner_repository.sql`.
2. Copy `services/collector/.env.example` to `.env`.
3. Install:
   `pip install -r services/collector/requirements.txt`
4. Start:
   `python -m uvicorn services.collector.app:app --reload --port 5200`
5. Open:
   `http://localhost:5200/docs`

## Example target

```json
{
  "name": "WWI Local",
  "server_identifier": "localhost\\SQLEXPRESS",
  "database_name": "WideWorldImporters",
  "environment_name": "Development",
  "credential_reference": "WWI_TARGET"
}
```

The repository stores the credential reference, never the password.

## Implemented API

- `POST /api/targets`
- `GET /api/targets`
- `GET /api/targets/{id}`
- `POST /api/targets/{id}/test-connection`
- `POST /api/collection-batches`
- `GET /api/collection-batches`
- `GET /api/collection-batches/{id}`
- `POST /api/collection-batches/{id}/start`
- `POST /api/collection-batches/{id}/complete`
- `POST /api/collection-batches/{id}/fail`

## Next slice

WC-03 through WC-06:
- Query Store runtime reader
- index usage and operational readers
- missing-index reader
- schema/index/constraint/size metadata reader
