"# AutomatedDatabaseTuning" 

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