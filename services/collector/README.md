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
