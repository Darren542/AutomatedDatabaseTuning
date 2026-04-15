# Recommender service (POC)

Generates index recommendations from:
- Missing index DMVs (as hints)
- Observed top-cost queries (from feature store)

Produces:
- A ranked list of CREATE INDEX recommendations
- A SQL file under `reports/` (optional) to apply in the demo

## Run
1) Copy `.env.example` → `.env` in repo root and fill in values.
2) Install deps:
   - `pip install -e services/recommender`
3) Run:
   - `autotuner-recommender`
