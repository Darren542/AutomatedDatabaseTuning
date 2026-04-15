# Demo Script (POC)

## Goal
Show workload → telemetry → recommendation → measured improvement.

## Steps
1. Run baseline workload (read-heavy).
2. Run collector to snapshot Query Store + DMVs into feature store tables.
3. Run recommender to generate top CREATE INDEX recommendation(s) + rationale.
4. Apply recommended index.
5. Re-run workload with same parameters.
6. Show before/after metrics and generated report.

## Evidence to show on screen
- Query Store top queries (duration/CPU/logical reads)
- Generated recommendation SQL
- Before/after metrics in report output
