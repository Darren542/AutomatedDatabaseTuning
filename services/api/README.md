# Automated tuner API

Install and start using [local development](../../docs/LOCAL_DEVELOPMENT.md). The composition root is `autotuner_api.app.create_app`. Database connections are opened by explicit repository/connection/collection/analysis operations, not by the liveness endpoint.

- `GET /api/v1/health`: process liveness, not database readiness.
- `/api/v1/targets`: connection testing, save and list targets; see [target API](../../docs/TARGET_API.md).
- `/api/v1/collections`: collect/browse persisted workload evidence; see [project frontend](../../docs/PROJECT_FRONTEND.md).
- `/api/v1/recommendations`: analyze stored evidence, list analyses and reopen details; see [Sprint 2 API and setup](../../docs/SPRINT_2_IMPLEMENTATION.md).

Interactive HTTP documentation is at `/docs`. Sprint 2 recommendations are advisory; this API has no tuning-SQL execution endpoint.

## Workflow and workload laboratory

Migration 006 adds `/candidate-sets`, `/recommendations/score`, `/cleanup` and `/simulator` operations. See [setup and contracts](../../docs/WORKFLOW_AND_SIMULATOR.md).
