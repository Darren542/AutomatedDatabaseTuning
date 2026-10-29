# Sprint 2 acceptance demonstration

Verified on October 28, 2026. Scope: FR-04, FR-05, FR-06 and FR-10 using deterministic synthetic collector evidence. This demonstrates functional acceptance; it does not measure real workload speedup. Browser checks were performed interactively, with screenshots. Selenium automation and a recorded video were not produced.

## Results

| Story | Acceptance demonstration | Result |
| --- | --- | --- |
| FR-04 | Generate from persisted missing-index and schema evidence; inspect table, keys, includes and source IDs | Pass: 2 CREATE candidates, no rejected fixture shapes |
| FR-05 | Compare narrow/read-heavy Orders with wide/write-heavy Events; inspect score components | Pass: Orders 112.7286, Events -2998.4348; Events has a 3110.7193 write penalty and Review status |
| FR-06 | Inspect advisory SQL, rationale, related query, estimated units, caveats and provenance; reopen a saved analysis | Pass: query 101/102 evidence, input hash, metadata/collection IDs and saved result preserved |
| FR-10 | Inspect duplicate DROP advice and protected RETAIN advice | Pass: 2 DROP suggestions, 4 RETAIN; protected PKs never droppable; 48-hour usage evidence displayed |
| Error handling | Missing collection, pending collection, unsafe policy/execution fields | Pass: 404/422, no fabricated analysis |
| Persistence | Reopen using a fresh application/client against the same SQL repository | Pass: identical saved result |

Backend: **140 tests passed**, including collector regressions, engine, service, repository and API checks. Frontend: **12 checks passed**. Production dashboard build passed. Combined unit and SQL-backed coverage of `recommender.engine`, `recommender.repository` and `recommender.service`: **96% statements** (engine 97%, repository 92%, service 100%). This coverage excludes frontend and the rest of the application. Existing Starlette/AnyIO deprecation warning remains.

Evidence: [backend JUnit](sprint2-evidence/backend-tests.xml), [core coverage](sprint2-evidence/core-coverage.json), [SQL-backed checks](sprint2-evidence/sql-acceptance.json), [frontend checks/build](sprint2-evidence/frontend-checks.txt).

## Repeatable demo setup

Use the project virtual environment and install the three local packages as shown in [implementation instructions](SPRINT_2_IMPLEMENTATION.md). The repository SQL connection settings in `.env` must allow creating an isolated database on the configured local server. Demo scripts accept only names beginning `AutoTuner_Sprint2_Demo_`; seeding refuses an existing database. They do not overwrite/drop databases or connect to monitored target databases.

From the repository root, create a uniquely named demo database:

```powershell
services\collector\.venv\Scripts\python.exe scripts/sprint2_demo.py --database AutoTuner_Sprint2_Demo_MYRUN --seed
services\collector\.venv\Scripts\python.exe scripts/sprint2_verify.py --database AutoTuner_Sprint2_Demo_MYRUN
services\collector\.venv\Scripts\python.exe scripts/sprint2_demo.py --database AutoTuner_Sprint2_Demo_MYRUN --serve --port 8093
```

Seeding applies migrations 001–005 in the isolated database, repeats 005 to check idempotency, stores synthetic metadata/query/hint/usage evidence and generates the initial analysis. Verification adds another analysis and one synthetic pending batch to check rejection. For this run, `AutoTuner_Sprint2_Demo_20261028_1` was created and remains available. To reuse it, omit `--seed` and run verification/server commands against that name. Its collection ID is `d99bab91-49d3-f111-990a-44e517fe2544`.

In a second PowerShell terminal:

```powershell
Set-Location dashboard/web
$env:AUTOTUNER_API_URL = 'http://127.0.0.1:8093'
npm run dev -- --port 5183 --strictPort
```

Open `http://127.0.0.1:5183`. These settings affect these demo processes; the normal repository configuration is unchanged. Stop both processes with Ctrl+C when finished. Database removal is a separate explicit operator action.

## Walkthrough for the sprint demonstration

1. Open **Candidate generator**. Select **Synthetic acceptance · read/write ranking** and click **Generate recommendations**. Show the 2 CREATE, 4 RETAIN and 2 DROP totals.
2. Filter action **CREATE**. Show Orders above Events. Inspect Orders: `CustomerId` key, `Payload` include, bracket-quoted CREATE SQL, read benefit and write/storage penalties. [Screenshot](sprint2-evidence/01-ranked-create.png).
3. Inspect Events. Show its higher write penalty, wide payload, negative net score and Review status. Expand query 102 to show SQL, execution count, observed duration/CPU/reads and the textual-association caveat. [Screenshot](sprint2-evidence/02-write-penalty.png).
4. Filter **DROP**. Inspect Orders: duplicate `IX_Orders_10`, keeper `IX_Orders_9`, 48 compatible hours, zero read deltas and positive maintenance. Show that SQL is advisory and no Apply action exists. [Screenshot](sprint2-evidence/03-drop-review.png).
5. Filter **RETAIN**, search `IX_Orders_1`. Show **Protected**, retention rationale and no structural-change SQL. [Screenshot](sprint2-evidence/04-protected-retain.png).
6. Clear search and filters. Open **Scoring engine**, then reload the page, navigate back to **Scoring engine** and reopen a **Saved analysis**. Show the same collection/input hash and result; generating again creates another saved analysis.
7. Show terminal output from `sprint2_verify.py`: SQL-backed generation, persistence across application instances, missing-batch 404 and pending-batch 422. Explain that a healthy collection without hints can legitimately have no CREATE opportunities.

Synthetic source observation times are fixed to make counter intervals deterministic. Collection creation timestamps reflect the actual seed run. They need not match. Do not present the synthetic 48-hour interval as a real two-day experiment.

## Regression commands

```powershell
services\collector\.venv\Scripts\python.exe -m pytest services/collector/tests services/api/tests services/recommender/tests -q
Set-Location dashboard/web
npm test
npm run build
```

The revised backlog and this evidence package are ready for the sprint submission. Upload and presentation/recording in the course system remain operator steps; no upload destination was supplied.
