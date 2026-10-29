# Project frontend and collector completion

The frontend now covers the full project workspace. Completed backend features are connected: saved targets, permission validation, target creation, collection execution, component progress, workload history filters, and batch summaries. Candidate generation, scoring, forecasting, safety/execution, reports, and platform automation have explicitly labelled placeholder pages. They show no fabricated recommendations or forecast metrics.

## Database preparation

Stop the API and collector before applying migrations. Existing installations with migrations 001–003 need only:

`sql/databases/repository/migrations/004_query_store_source_window.sql`

Run this file in SSMS against AutoTunerRepository. It changes the canonical Query Store unique key to include the interval start time. Query Store can reuse numeric IDs after clearing; keeping the interval start in the key prevents later evidence overwriting earlier batches. Existing evidence and links are preserved, and the migration can be rerun. No SQL files are automatically applied by the application.

For a fresh installation, run repository migrations 001 through 004 in order. No target database schema changes are required. Collector accounts must have telemetry/metadata visibility, including source-state/server DMVs, and must lack database/table ALTER permissions. Use the established restricted collector credential rather than an administrator account. The save endpoint now validates readiness using the credential reference configured on the server.

The existing `WWI Local` Windows target was observed to have ALTER permission. For a dedicated login, an optional reviewed setup template is provided at `sql/databases/wwi/setup/configure_collector_permissions.sql`. It requires an existing non-admin login and does not contain or create passwords. Configure its credential reference in the API environment, then add/test/save a SQL-authenticated target. No permission changes were applied automatically.

## Start the application

From the repository root, use the project's current collector virtual environment:

```powershell
services\collector\.venv\Scripts\python.exe -m pip install -e "services/collector[dev]" -e "services/api[dev]"
services\collector\.venv\Scripts\python.exe -m autotuner_api
```

The API reads its startup and repository settings from the root `.env` (environment variables override them). SQL target credential references also resolve from this file or environment: for `WWI_COLLECTOR`, configure `WWI_COLLECTOR_SQL_USERNAME` and `WWI_COLLECTOR_SQL_PASSWORD`. These secrets are never saved by the browser form.

In another terminal:

```powershell
Set-Location dashboard/web
npm ci
npm run dev
```

Use the URL printed by Vite, normally http://127.0.0.1:5173. The `/api` proxy forwards to http://127.0.0.1:8080. Set `AUTOTUNER_API_URL` in the Vite terminal for a different backend address. Both processes need restarting after pulling backend or proxy changes. A production host must configure its own `/api` routing.

## Operator workflow

1. Open Database targets. Existing targets load from the repository.
2. Add a target, test the connection, and review all capability checks. A successful connection alone does not mean the collector is ready. Saving revalidates the configured server credentials.
3. Select a target and open Workload collector. Choose an automatic window or explicit local-time start/end values, and optionally force metadata refresh.
4. Start collection. The browser creates a Pending batch and invokes the completed synchronous collector API. Component results are polled while it runs.
5. Inspect status, completeness, source/reset indicators, Query Store totals, effective/requested windows, and the current watermark.
6. Browse Workload history by target, status, or creation date. Creation dates are filtered in the browser's local timezone and sent as UTC instants. Results are limited to 100 matching batches.
7. If a process stopped with a batch left Collecting, inspect it and choose Cancel inactive batch. The server rejects cancellation while a collector owns the target lock. Create a new batch to retry; terminal batches remain immutable.

Zero Query Store rows are valid for short windows while source intervals remain open. Metadata skipped by cadence counts as healthy completion. Query Store totals describe a single batch; overlapping batches can share canonical evidence, so their totals must not be summed. The metadata source and target watermark shown in a summary describe current target state.

## Reliability changes

- Repository session-owned application locks serialize collection per target across API processes. Different targets can collect independently. Locks are released on normal completion and session loss.
- State transitions use an expected-status predicate to prevent lost updates. A Collecting batch cannot be silently rerun.
- An explicit inactive-batch cancellation endpoint provides restart recovery; retries create new history records.
- API UTC timestamps include timezone offsets; mixed aware/naive request dates normalize before comparison.
- Required capability checks include source state, operational stats, missing-index evidence, and metadata size access.
- Component failures report safe exception types instead of dumping diagnostic tracebacks that might contain SQL/credentials.
- Repository password representations are hidden and ODBC attribute values are quoted.

## Checks and remaining scope

```powershell
services\collector\.venv\Scripts\python.exe -m pytest services/api/tests services/collector/tests --import-mode=importlib
Set-Location dashboard/web
npm test
npm run build
```

Scheduling, true worker queues, interruption of active SQL commands, large-history pagination, bulk persistence performance, retention, production authentication/secret management, and formal NFR benchmarks remain later work. This completes the interactive collector workflow for the current capstone phase, not the future tuning engines or production deployment requirements.
