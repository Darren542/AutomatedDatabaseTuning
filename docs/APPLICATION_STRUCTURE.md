# Application structure

Sprint 1 begins by adding an HTTP application around the existing SQL/Python prototype. Preserve the prototype as a runnable experiment while migrating its behavior incrementally.

## Component ownership

| Location | Responsibility | Current state |
| --- | --- | --- |
| `services/api/src/autotuner_api` | Application composition, startup settings, versioned HTTP routes | Health endpoint implemented |
| `services/collector` | Target connection checks and telemetry collection | FR-01 target model and connection validation implemented; telemetry remains FR-02 |
| `services/recommender` | Candidate generation and scoring; later forecasting integration | Existing placeholder |
| `services/autorunner` | Interactive prototype experiment entry point | Preserved |
| `sql/shared` | Reusable capture, comparison, and candidate SQL | Prototype SQL retained |
| `sql/databases` | Database-specific setup, fixtures, and workloads | Prototype SQL retained |
| `dashboard/web` | React presentation and HTTP client | Existing skeleton |
| `infra` and `.github` | Deployment scaffolding and CI | Existing scaffolding; separate backlog tasks |

## Boundaries for upcoming work

The initial application is a modular Python backend, not a fleet of independently deployed services. Existing collector and recommender packages retain their responsibilities and can be installed alongside the API when implemented.

HTTP routes call application services; they do not embed SQL, scoring, or job execution logic. Collector modules return normalized telemetry. A persistence layer owns target/run records, migrations, transactions, and retry-safe writes under FR-03. Shared DTOs should be introduced with those real interfaces, not as speculative empty packages.

Collection will use persisted job/run identifiers with a start operation and a status operation. Durable execution and recovery are implemented with FR-02/FR-03; an in-memory background task is not durable job history. Do not run the interactive autorunner inside an HTTP request.

The Safety Controller will own authorization/policy checks and a separately privileged executor. Reporting UI accesses data through the API; it does not receive database credentials or execute SQL. The ML forecaster will consume persisted history and supply forecasts to scoring; it does not execute tuning changes.

## Prototype migration

Keep `services/autorunner/autotuner_poc_runner.py` and its relative SQL paths intact. Migrate capture behavior into the collector with tests when implementing FR-02. Query Store clearing remains a demo behavior and must not be copied into continuous collection. Existing README quick-start paths and CI SQL paths are legacy; use LOCAL_DEVELOPMENT.md for the new application and correct CI in its own task.

## Scope of this change

Implemented: installable API package, composition root, validated host/port configuration, liveness route, API contract/settings tests, and local startup documentation.

Deferred: FR-01 target registration, SQL connectivity, persistence/migrations, background execution, dashboard integration, CORS/authentication policy, secret storage, and CI expansion. The API binds to loopback by default and is a local development foundation.

## FR-01 progress

The collector now owns immutable target metadata, transient SQL credentials, and a read-only connection-validation service. See [Target validation](TARGET_VALIDATION.md). Target registration APIs, persistence, and UI remain pending.
