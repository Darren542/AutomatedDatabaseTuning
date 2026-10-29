# Collection, candidate and scoring workflow

The Candidate Generator and Scoring Engine now have separate responsibilities and persistence. This extends Sprint 2 without adding automatic index execution.

| Workspace | Responsibility | Saved output |
| --- | --- | --- |
| Database targets | Register/test a SQL Server database and manage its repository history | Target configuration and credential reference |
| Workload collector / history | Collect a labelled workload window; inspect component outcomes and continuity | Collection and source evidence |
| Candidate generator | Select a collection, check readiness, discover index shapes, inspect coverage/evidence, select candidates | Unscored candidate set with frozen input snapshot |
| Scoring engine | Select a candidate set, change weights/selection, rank results and compare scoring runs | Scoring run linked to the candidate set |
| Workload simulator | Offer seeded traffic, change read/write/hot-key patterns, collect periodic snapshots | Run configuration, statistics, phase controls and collection/result links |

## Required setup

1. Apply migrations 001–005 if not already installed. Then apply **`sql/databases/repository/migrations/006_workflow_and_simulator.sql`** in the repository database. Check its `USE` statement if your repository has a different name. Migration 006 is rerunnable and creates candidate-set/simulator storage plus the optional candidate-set link on analyses.
2. Restart the API and dashboard. There are no new Python/npm dependencies. Existing local installation instructions still apply.
3. For simulated traffic, select a **disposable user database** in SSMS and apply **`sql/simulator/001_simulator_sandbox.sql`** there. The script creates a dedicated `TunerSim` schema, an enabled configuration marker and 20,000 sample orders. It preserves existing sandbox data on rerun. Register this database as a target.
4. Review/run the optional Query Store statements at the end of the sandbox script. A one-minute interval and capture mode ALL make short experiments easier to inspect. These settings affect the selected database, so they are commented out in the setup file.
5. The simulator connection needs SELECT on `TunerSim.Configuration` and `TunerSim.Orders`, plus INSERT/UPDATE on `TunerSim.Orders` for write traffic. The collector still needs its normal Query Store/DMV/metadata permissions. No DDL permission is needed at runtime.

Migration 006 and the sandbox script were applied **only to disposable acceptance databases** during verification. They have not been applied to your normal repository or application databases.

## Ordinary analysis flow

1. Save/select a target and test access.
2. Create a labelled collection. Automatic incremental or explicit historical windows are supported. Enable Force metadata refresh when schema metadata is unavailable/old.
3. Inspect the source/component results. In the collection detail or history row, choose **Use collection for candidates / Generate candidates**.
4. Candidate Generator checks required components, metadata freshness and source state. It reports missing-index hint and existing-index counts. Generate a candidate set, inspect index shapes/coverage and select the candidates to include. There are **no weighted scores or ranks on this page**.
5. Choose **Continue to scoring**. The selected candidate set and IDs are carried forward. Set read, write and storage weights, then choose **Run scoring**.
6. Inspect ranked scores, component values, SQL, rationale, query associations and provenance. Re-run with different weights and use **Compare with scoring run** to compare the same candidate IDs over identical evidence.

Generating a candidate set does not calculate weighted scores. Scoring consumes the set's saved InputJson; it does not collect again or fetch current target metadata. Input hashes remain the same across weight changes. New target activity/schema changes require another collection and candidate set. RETAIN/DROP remain conservative rule-based advice.

Existing all-in-one Sprint 2 analyses remain accessible through **Earlier analyses (before the workflow split)** on Scoring Engine. **Create candidate set from saved evidence** creates an unscored set from the old analysis's input snapshot. The old analysis is preserved. The older analyze API/CLI remains compatible, while the main UI uses the separate workflow.

## Cleanup controls

- **Workload history / collection detail → Delete** removes one collection and candidate sets/scoring runs that depend on its source or metadata snapshot.
- **Database targets → Clear collected data** keeps the target configuration but removes its collections, results, simulation history and collection watermarks.
- **Database targets → Delete target** removes that repository configuration and its dependent history.

Each action first opens a count preview. Type the displayed target name or collection UUID exactly to enable deletion. A preview token detects changed records between preview and execution. Cleanup runs transactionally, blocks active collectors/simulators and preserves canonical Query Store rows still referenced by another collection. It never connects to the monitored database.

Deleting metadata can require Force metadata refresh before further generation. Clearing watermarks means the next automatic collection starts its configured lookback again; Query Store may still contain those intervals. Deleting repository history does not undo already committed simulator writes, drop a database/table, or remove credentials from server environment configuration. A single deleted collection can leave historical simulator links pointing to a removed snapshot; clearing all target data also removes those runs.

Analyses/candidate sets are append-only during ordinary use. Explicit confirmed cleanup is the intentional deletion exception.

## Poisson workload laboratory

Select the sandbox target and open **Workload simulator**. Choose a preset or edit the phases:

- Duration and offered requests/second (0–100).
- Relative customer-read, product-read, INSERT and UPDATE weights.
- Hot-key traffic percentage and hot customer/product IDs.
- Seed, maximum concurrent requests (1–8), request budget and write-attempt budget.
- Automatic collections every 30–3,600 seconds and optional candidate generation/scoring after eligible collections.

The **Read → product → write** preset enables controlled writes explicitly in the form; review the checkbox and budgets before starting. A write-weighted run requires the write opt-in. Write attempts are capped at 10,000 and requests at 100,000 per run; the default UI budget is smaller. A run's offered traffic lasts at most one hour. No arbitrary SQL can be supplied.

The fixed read templates select at most 200 orders using customer/product predicates and a sort. These exercise full optimization and can produce missing-index hints. Simple COUNT/SUM-only templates were rejected during SQL verification because their trivial plans did not produce hints. INSERT/UPDATE affect only sandbox orders; updates target the seeded order ID range.

Exponential inter-arrival times generate a piecewise Poisson offered process. Requests run in a bounded worker pool. Busy/late arrivals and writes beyond the attempt budget are dropped and counted instead of queued indefinitely. The chart compares configured offered rate with achieved completions/second; it does not imply that admitted requests still form an unconstrained Poisson process. Database timing, concurrency, dropped arrivals and the timing of live controls affect the realized result even with the same seed.

The monitor shows offered/completed/dropped/failed counts, writes, affected rows, latency, phase transitions and linked snapshots. **Apply phase live** replaces the remaining planned phases, subject to the run's original write permission and one-hour limit. Each change is persisted with its timestamp. **Stop / recover run** stops new arrivals and drains in-flight work; it also recovers an interrupted job after an API restart, provided no worker still holds the target's simulation lock.

Runs are local background jobs owned by the API process, not durable scheduled jobs. Use a single API worker for live control. At most four runs can be active in that process, and only one simulator may own a target. Keep the API running during an experiment. Historical runs/configuration/statistics survive restarts; traffic does not automatically resume.

Automatic collectors run independently of request scheduling, one collection at a time. Completed/Partial snapshots are analyzed when eligible. Closed Query Store intervals appear later than live request counters. Missing-index DMV evidence is cumulative and can retain earlier opportunities; this feature does not implement a forecasting model or automatically apply indexes. Use the saved snapshot comparisons to observe changes in advice.

## HTTP operations

- `POST /api/v1/candidate-sets` with `batch_id`; GET list/detail; GET `candidate-sets/eligibility/{batch_id}`.
- `POST /api/v1/candidate-sets/from-analysis/{analysis_id}` reuses a saved input snapshot.
- `POST /api/v1/recommendations/score` with `candidate_set_id`, optional `candidate_ids`, and `weights`.
- `GET /api/v1/cleanup/targets/{id}/preview?delete_target=false` or `/cleanup/collections/{id}/preview`.
- DELETE the corresponding resource with `confirmation`, `preview_token`, and optional `delete_target`.
- `POST /api/v1/simulator/runs`; GET runs/detail; POST `runs/{id}/phase` and `runs/{id}/stop`.

Interactive request schemas are at `/docs`.

## Verification and demo

160 backend tests and 13 frontend checks passed; the production dashboard build passed. New tests cover unscored discovery, frozen-input rescoring, earlier-analysis reuse, seeded arrival behavior, unsafe/invalid plans, write/queue limits, stop behavior, recovery races and cleanup confirmation guards.

SQL-backed acceptance used `AutoTuner_Sprint2_Demo_Flow_20261028` and the separate target `AutoTuner_Workload_Flow_20261028_Final`. The run completed **139 requests, zero failures and five write attempts/affected rows**, recorded a live phase change and saved two complete collection/candidate/scoring snapshots. The later set included both `[ProductId, Status]` and `[CustomerId, Status]` CREATE shapes. This is functional acceptance on synthetic data, not a performance benchmark.

Cleanup checks removed only test-created records, verified that dependent sets/scores were removed and shared Query Store evidence survived, and exercised both purge-with-target-retained and target deletion. Migration 006 rerun succeeded.

See [SQL acceptance evidence](workflow-evidence/sql-acceptance.json), [discovery screenshot](workflow-evidence/discovery.png), [scoring screenshot](workflow-evidence/scoring.png), [simulator screenshot](workflow-evidence/simulator.png), and [cleanup preview](workflow-evidence/cleanup.png).

To reproduce the complete SQL acceptance suite, choose fresh disposable names:

```powershell
services\collector\.venv\Scripts\python.exe scripts/sprint2_demo.py --database AutoTuner_Sprint2_Demo_Flow_MYRUN --seed
services\collector\.venv\Scripts\python.exe scripts/workflow_acceptance.py --repository AutoTuner_Sprint2_Demo_Flow_MYRUN --target AutoTuner_Workload_Flow_MYRUN
```

This creates/reuses only databases with the required test prefixes, sets Query Store options in its disposable target and performs bounded sandbox writes and test-record cleanup. It never drops databases. The acceptance databases are retained for review. The original Sprint 2 demo database requires migration 006 before reuse with this version.

For a browser demonstration, generate candidates from a completed collection, send them to Scoring, change a weight and compare runs. Then show the simulator's phase controls/history/snapshots and open a cleanup preview. Use the separate test databases for destructive demonstrations.

References: [Python exponential arrivals](https://docs.python.org/3/library/random.html#random.expovariate), [Microsoft Query Store configuration](https://learn.microsoft.com/en-us/sql/t-sql/statements/alter-database-transact-sql-set-options?view=sql-server-ver17).
