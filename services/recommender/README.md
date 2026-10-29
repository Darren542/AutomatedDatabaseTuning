# Recommendation service

Generates advisory CREATE/RETAIN/DROP recommendations from persisted collector evidence. Includes deterministic scoring, conservative protection rules and append-only analysis snapshots. No target tuning SQL is executed.

Install all local packages together and apply repository migration 005. See [Sprint 2 setup, rules and API](../../docs/SPRINT_2_IMPLEMENTATION.md), [task backlog](../../docs/SPRINT_2_BACKLOG.md) and [acceptance demonstration](../../docs/SPRINT_2_ACCEPTANCE.md).

From the repository root:

```powershell
services\collector\.venv\Scripts\autotuner-recommender.exe --batch-id <collection-UUID>
```

## Candidate sets and scoring runs

Discovery now persists unscored candidate sets; scoring reuses their frozen inputs with selected weights. See [workflow instructions](../../docs/WORKFLOW_AND_SIMULATOR.md). Earlier analyses can supply saved evidence without rescanning.
