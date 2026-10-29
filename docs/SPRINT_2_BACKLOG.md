# Sprint 2 backlog

Scope: FR-04 candidate generation, FR-05 scoring/ranking, FR-06 explanation, FR-10 CREATE/RETAIN/DROP advice. Implementation is advisory; target DDL execution and approval are Sprint 3.

| Task | Story | Work | Estimate | Status |
| --- | --- | --- | --- | --- |
| B-015 | FR-04 | Load one collection's missing-index evidence and provenance | 4h | Done |
| B-016 | FR-04, FR-10 | Load historical schema/index metadata and source-compatible observations | 4h | Done |
| B-017 | FR-04 | Parse column identifiers, merge duplicates, detect coverage | 4h | Done |
| B-018 | FR-05 | Calculate transparent read-benefit and workload-frequency features | 4h | Done |
| B-019 | FR-05 | Calculate write, width, and storage/maintenance penalties | 4h | Done |
| B-020 | FR-05, FR-10 | Validate key feasibility and block protected/ambiguous DROP advice | 4h | Done |
| B-021 | FR-10 | Implement conservative redundant/unused index RETAIN/DROP rules | 4h | Done |
| B-022 | FR-05, FR-06 | Persist immutable analysis results, inputs, policy, and evidence links | 3h | Done |
| B-023 | FR-04, FR-05 | Add analysis API and ranked/filterable recommendations UI | 4h | Done |
| B-024 | FR-06 | Add detail view with SQL, score components, query evidence, and caveats | 4h | Done |
| B-025 | All four | Unit/API/repository tests and reproducible acceptance demonstration | 5h | Done |

Initial estimates are the specification's estimates, not actual time spent. B-015 through B-025 are implemented and verified. See [acceptance results and walkthrough](SPRINT_2_ACCEPTANCE.md) and [revised workbook](Sprint_2_Revised_Backlog.xlsx). Broader Sprint 1 CI/security closeout remains a separate backlog item.

## Acceptance checklist

- [x] FR-04: a known missing-index fixture produces a CREATE recommendation with table, keys, includes, and source evidence.
- [x] FR-05: a comparable read-heavy candidate ranks above a write-heavy/wide candidate; visible score components explain the order.
- [x] FR-06: detail exposes SQL, target, query associations, predicted impact units, rationale, caveats, and persisted provenance.
- [x] FR-10: redundant/low-value fixtures produce DROP/RETAIN advice, and PK/unique/constraint-supporting indexes never become DROP recommendations.
- [x] Evidence-empty or incomplete collections produce explicit outcomes, not fabricated opportunities.
- [x] SQL migrations are delivered as files; applying migrations and executing tuning SQL are separate operator actions.


## User stories and completed subtasks

| Story | Tasks | Outcome |
| --- | --- | --- |
| FR-04 Generate index candidates | B-015, B-016, B-017, B-023 | Collection-scoped CREATE advice with deduplication, coverage and provenance |
| FR-05 Score and rank tuning candidates | B-018, B-019, B-020, B-022, B-023 | Persisted read/write/storage components and ranked/filterable results |
| FR-06 Explain each recommendation | B-022, B-024 | Detail view with SQL, rationale, query evidence, estimated units and caveats |
| FR-10 Identify redundant or low-value indexes | B-016, B-020, B-021 | Conservative CREATE/RETAIN/DROP advice with protected-index rules |

Completed task checklists for Trello:

- [x] B-015: load missing-index rows for the selected successful collection; retain batch/group/index handles.
- [x] B-016: load metadata at/before the source snapshot; select a same-epoch baseline; load usage, operational and query evidence.
- [x] B-017: parse quoted identifiers; normalize equality keys; merge includes and repeated hints; suppress covered candidates; identify overlapping alternatives.
- [x] B-018: calculate cost/impact/frequency read benefit; expose its units and component values.
- [x] B-019: calculate base-table write pressure, index width, storage and separate operational maintenance factors; handle unknown/reset counters.
- [x] B-020: validate key types/size/count; protect PK/unique/constraints and conservatively protect foreign-key participants.
- [x] B-021: compare unchanged index definitions; preserve duplicate keepers; require sufficient observation before unused-index DROP advice.
- [x] B-022: deliver migration 005; save input/result JSON, policy, engine version, hash and evidence IDs; reopen exact saved results.
- [x] B-023: expose analyze/list/detail endpoints; connect Candidate generator and Scoring engine; add action/status/search filters.
- [x] B-024: show advisory SQL, score breakdown, rationale, expandable query evidence and provenance; distinguish rule-based RETAIN/DROP decisions.
- [x] B-025: add engine/service/repository/API/filter checks; verify SQL persistence and migration idempotency; capture browser demonstration and repeatable operator steps.

## Sprint closeout

140 backend tests and 12 frontend checks passed. Production build and isolated SQL-backed acceptance passed. See the evidence directory and acceptance guide. Selenium automation remains deferred under the agreed scope. The guide contains a screenshot walkthrough, not a recorded video.

Remaining operator steps: apply migration 005 to the normal repository, run the updated application against real collected evidence, and upload the revised backlog/demo evidence to the course submission destination. The isolated acceptance database remains available for the demo. No monitored database tuning SQL was executed.

Future implementation stays in Sprint 3: approval/execution, before/after comparison, regression detection, rollback, settings and action audit. ML remains scheduled separately. Broader Sprint 1 CI/security closeout is not represented as completed by this sprint.

## Follow-up workflow improvements

The following additional work was requested after the original Sprint 2 delivery. These items have no agreed hour estimates and do not change the original 44-hour estimate.

| Task | Work | Status |
| --- | --- | --- |
| WF-01 | Separate unscored candidate discovery from weighted scoring | Done |
| WF-02 | Persist frozen candidate sets and selected scoring runs | Done |
| WF-03 | Carry collections/candidates through UI navigation and report eligibility | Done |
| WF-04 | Compare weight changes and preserve access to earlier analyses | Done |
| WF-05 | Preview and confirm collection/target-data/target deletion; preserve shared evidence | Done |
| WF-06 | Generate seeded, bounded Poisson requests with relative query/hot-key distributions | Done |
| WF-07 | Support controlled sandbox INSERT/UPDATE, live phases, stop and interrupted-run recovery | Done |
| WF-08 | Collect periodic experiment snapshots and optionally generate/score candidates | Done |
| WF-09 | Deliver migration 006, sandbox SQL and operator instructions | Done |
| WF-10 | Verify regression, SQL-backed behavior and browser workflow | Done |

See [workflow instructions and acceptance evidence](WORKFLOW_AND_SIMULATOR.md). The Excel backlog remains the original Sprint 2 task snapshot; this section records the subsequent unestimated additions.
