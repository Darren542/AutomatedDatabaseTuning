# Decisions (ADR-lite)

## D1 — Use SQL Server Query Store as primary workload truth
**Reason:** Query Store provides stable historical query/runtime/plan data enabling before/after comparisons and regression detection.

## D2 — Treat missing-index DMVs as hints, not truth
**Reason:** Missing-index suggestions can be noisy and may cause redundant indexes or write amplification if applied blindly.

## D3 — POC will apply changes manually
**Reason:** For a proof-of-concept, demonstrate the loop end-to-end safely. Full auto-apply with rollback is a later milestone.

## D4 — Polyglot implementation
- Python for telemetry, scoring, and ML forecasting
- React for dashboard visualization
- SQL scripts for schema/workload repeatability
