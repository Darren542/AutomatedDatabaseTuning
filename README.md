# SQL Server Database Workload Auto‑Tuner (POC)

This repository is a **proof-of-concept** for an automated tuning loop on **SQL Server**:

1. Run a repeatable workload (read-heavy + write-heavy).
2. Collect telemetry from **Query Store** + select **DMVs** into a small *Feature Store* schema.
3. Generate index recommendations (CREATE INDEX) using missing-index hints + simple scoring.
4. Apply 1–2 recommendations (manual for POC).
5. Re-run workload and show **before vs after** metrics (latency/CPU/logical reads).

> The POC is intentionally small: it demonstrates the idea end-to-end without implementing a full production autotuner.

## Repo layout

- `docs/` – proposal artifacts, decisions, demo script
- `sql/` – schema, seed, workload scripts, Query Store setup
- `services/collector/` – Python telemetry collector (Query Store + DMVs → feature store tables)
- `services/recommender/` – Python recommender (candidates + scoring + report output)
- `dashboard/web/` – React dashboard (optional for POC; can start as static view)
- `infra/compose/` – docker-compose scaffolding
- `.github/workflows/` – CI scaffolding

## Quick start (POC flow)

1. Create a SQL Server database and run:
   - `sql/setup/enable_query_store.sql`
   - `sql/schema/01_schema.sql`
   - `sql/seed/seed.sql`
2. Run a baseline workload:
   - `sql/workloads/read_heavy.sql`
3. Collect telemetry:
   - `python -m services.collector` (see `services/collector/README.md`)
4. Generate recommendations:
   - `python -m services.recommender` (see `services/recommender/README.md`)
5. Apply recommended index (generated under `reports/`) and re-run workload.

## Notes

- Secrets/config go in `.env` (copy from `.env.example`). Do not commit `.env`.
- For the capstone, use PRs into `dev`, then merge to `main` for stable demos.


/
├─ README.md
├─ .gitignore
├─ .editorconfig
├─ docs/
│  ├─ PROJECT_LOG.md
│  ├─ DECISIONS.md
│  ├─ SYSTEM_DIAGRAM.md
│  ├─ DEMO_SCRIPT.md
│  └─ ROADMAP.md
├─ sql/
│  ├─ setup/          (Query Store enablement/config)
│  ├─ schema/         (tables/indexes)
│  ├─ seed/           (seed scripts/data generator)
│  └─ workloads/      (read-heavy, write-heavy)
├─ services/
│  ├─ collector/      (Python: pulls Query Store/DMVs → feature store)
│  │  ├─ src/
│  │  ├─ tests/
│  │  ├─ pyproject.toml
│  │  └─ README.md
│  ├─ recommender/    (Python: candidates + scoring + ML forecast later)
│  │  ├─ src/
│  │  ├─ tests/
│  │  ├─ pyproject.toml
│  │  └─ README.md
│  └─ api/            (Optional: Node/.NET API to serve dashboard)
│     └─ README.md
├─ dashboard/
│  ├─ web/            (React)
│  │  ├─ package.json
│  │  └─ README.md
├─ infra/
│  ├─ docker/         (Dockerfiles)
│  └─ compose/        (docker-compose.yml)
└─ .github/
   └─ workflows/
      ├─ ci-python.yml
      ├─ ci-react.yml
      └─ ci-sql-lint.yml
## Full implementation foundation

The new API starts independently of the preserved SQL prototype. See [Local development](docs/LOCAL_DEVELOPMENT.md) for current startup commands and [Application structure](docs/APPLICATION_STRUCTURE.md) for component ownership and migration boundaries. The earlier quick-start section describes the legacy scaffold.
