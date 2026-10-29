# Database Tuner dashboard

The project workspace connects saved targets, capability tests, collection runs, component progress, and workload history. Future tuning modules have labelled placeholder pages.

See [Project frontend and collector completion](../../docs/PROJECT_FRONTEND.md) for setup, required SQL migration, and the operator workflow.

From this folder, run `npm ci`, `npm run dev`, `npm test`, and `npm run build`. The Python API must run separately.

## Sprint 2 recommendations

Candidate generator and Scoring engine now use the analysis API. See [setup and migration 005](../../docs/SPRINT_2_IMPLEMENTATION.md) and the [acceptance walkthrough](../../docs/SPRINT_2_ACCEPTANCE.md). ML, execution and rollback remain placeholders.

## Separated workflow

Candidate Generator discovers/reviews shapes; Scoring Engine owns weighting, ranking and comparisons. The main UI also provides confirmed repository cleanup and a controlled Poisson workload simulator. See [workflow setup](../../docs/WORKFLOW_AND_SIMULATOR.md).
