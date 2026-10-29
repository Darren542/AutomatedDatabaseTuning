# Sprint 2: recommendations

Implemented FR-04, FR-05, FR-06 and FR-10 from **ProductDevelopmentTrack-RequirementsSpec**. The older prototype workbook uses different FR identifiers; use the current specification's identifiers for these stories.

## Install and use

From the repository root, install all three local packages together:

```powershell
services\collector\.venv\Scripts\python.exe -m pip install -e "services/collector[dev]" -e "services/recommender[dev]" -e "services/api[dev]"
```

Apply `sql/databases/repository/migrations/005_recommendation_analysis.sql` in SSMS to the configured repository database after migrations 001–004. Check the script's `USE [AutoTunerRepository]` when using a differently named repository. Migration 005 creates `dbo.RecommendationAnalysis` and can be run again safely. It does not change monitored databases. Migration 005 was verified in the isolated acceptance database; it has **not** been applied to your normal repository.

Start the API and dashboard using `LOCAL_DEVELOPMENT.md`. Collect workload evidence, enabling **Force metadata refresh** when metadata is unavailable or old. Open **Candidate generator** or **Scoring engine**, select the collection and click **Generate recommendations**. Filter by action, status or table/index name, then inspect a recommendation. **Saved analysis** reopens persisted results.

The API requires a Completed/Partial collection with successful source-state, runtime, missing-index, index-usage and operational components. Schema metadata must be from the same database epoch, observed at or before the source snapshot and within 24 hours of it. An eligible collection with no missing-index opportunities produces no fabricated CREATE candidates.

## Components and HTTP contract

- `recommender.engine`: pure, deterministic candidate extraction, coverage, scoring and protection rules.
- `recommender.repository`: reads stored collector evidence and writes append-only analysis snapshots. It never connects to a target database.
- `recommender.service`: load, analyze, persist.
- `POST /api/v1/recommendations/analyze`: `{"batch_id":"<UUID>"}`. Optional `weights` supports `read_weight`, `write_weight`, `storage_weight`, each finite and between 0 and 100. Returns 201 with the saved analysis. Unknown fields, including execution flags, are rejected.
- `GET /api/v1/recommendations/analyses?target_id=<UUID>&limit=50`: saved analysis summaries.
- `GET /api/v1/recommendations/analyses/<analysis_id>`: exact saved result.
- Missing resources return 404; ineligible evidence/policies return 422; repository connectivity errors return a generic 503.

The CLI accepts an explicit collection ID and prints the persisted advisory result:

```powershell
services\collector\.venv\Scripts\autotuner-recommender.exe --batch-id <collection-UUID>
```

Each run creates a new analysis. The application exposes no update/delete operation for analyses. Input JSON, SHA-256 input hash, engine version, policy, result, source collection and metadata IDs are preserved. This is application-level append-only storage; database administrators retain their normal ability to modify database records.

## Candidate and scoring rules

Bracket-quoted DMV columns are parsed as identifiers, including escaped closing brackets and commas inside identifiers. Equivalent equality keys are normalized, compatible include lists are merged, and repeated hints use the maximum benefit rather than double-counting it. Enabled, unfiltered rowstore indexes and implicit clustered keys are checked for coverage. Alternative overlapping key shapes remain separate options with warnings.

Unsupported/computed columns, unknown metadata, MAX keys, excessive key width/count and unsafe identifier shapes are rejected. The implementation uses SQL Server's 32-key-column and 1,700-byte nonclustered-key limits; older server versions may require stricter limits.

CREATE scores are transparent heuristic points:

- Read benefit uses optimizer missing-index cost, impact and observed seek/scan frequency with logarithmic scaling.
- Write penalty uses reset-compatible base-table maintenance statement deltas per hour and estimated index width. It does not sum every index's updates as table writes.
- Storage uses row count, declared widths, 16 bytes of row overhead and a 20% planning overhead. MAX included values assume 4,096 bytes.
- Maintenance includes storage and, when available, compatible operational leaf-write deltas. Leaf row operations and usage maintenance statements remain separate units.
- Net score applies the stored read/write/storage weights. Negative scores or unavailable write pressure require review.

These are **not calibrated millisecond predictions or measured performance improvements**. `latency_change_ms` is unavailable. Query associations use schema-qualified table references in stored SQL after stripping comments/literals; they are explicitly textual associations, not execution-plan proof.

## RETAIN and DROP rules

PK, unique, unique-constraint, special, filtered, disabled and constraint-supporting indexes remain protected. Because collected foreign-key metadata does not map its columns, all indexes on participating tables are conservatively protected.

DROP advice requires unchanged definitions, compatible SQL Server/database epochs, nonnegative usage deltas, zero observed reads and positive maintenance. Exact duplicates need at least 24 compatible hours and preserve a keeper; other unused indexes need at least 168 hours. Missing baselines, restarts/resets and changed definitions result in RETAIN advice. Rare workloads can still need an apparently unused index, so every DROP remains a manual-review suggestion. RETAIN/DROP are rule-based decisions, not CREATE benefit scores or quantified storage savings.

No SQL execution/approval endpoint is included. Approval, apply, before/after validation, rollback, policy-settings UI and action audit belong to Sprint 3. ML forecasting remains a placeholder.

## References

- [Microsoft: missing-index suggestion limitations](https://learn.microsoft.com/en-us/sql/relational-databases/indexes/tune-nonclustered-missing-index-suggestions?view=sql-server-ver17)
- [Microsoft: SQL Server capacity limits](https://learn.microsoft.com/en-us/sql/sql-server/maximum-capacity-specifications-for-sql-server?view=sql-server-ver17)
- [Microsoft: index usage statistics and resets](https://learn.microsoft.com/en-us/sql/relational-databases/system-dynamic-management-views/sys-dm-db-index-usage-stats-transact-sql)

See [acceptance demonstration](SPRINT_2_ACCEPTANCE.md) and [revised task backlog](SPRINT_2_BACKLOG.md).
