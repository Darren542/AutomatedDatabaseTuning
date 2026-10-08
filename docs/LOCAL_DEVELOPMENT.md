# Local development

Run the commands below in PowerShell from the repository root. Python 3.10 or newer is required. The API foundation runs without SQL Server or an ODBC driver.

## Install and run the API

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e "services/collector[dev]" -e "services/api[dev]"
# Optional: copy only if .env does not already exist.
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
.\.venv\Scripts\python.exe -m autotuner_api
```

Open http://127.0.0.1:8080/api/v1/health or http://127.0.0.1:8080/docs. Stop with Ctrl+C. The installed `autotuner-api` command is an equivalent entry point.

Settings are read from `.env` in the launch directory; environment variables override that file. `AUTOTUNER_API_HOST` defaults to `127.0.0.1`; `AUTOTUNER_API_PORT` defaults to `8080`. Invalid settings fail before the server starts. Existing SQLSERVER settings are not consumed by this API foundation.

## Backend checks

```powershell
.\.venv\Scripts\python.exe -m pytest services/api/tests
```

These tests exercise HTTP responses and configuration without SQL Server. They are not browser E2E tests.

## Existing dashboard

With Node.js/npm installed, run in a second terminal:

```powershell
Set-Location dashboard/web
npm ci
npm run dev
```

Use the URL printed by Vite. The dashboard now provides target configuration and Test Connection. Start the API as above, use `localhost\SQLEXPRESS` / `WideWorldImporters`, and enable certificate trust for the local demo. See [Dashboard instructions](../dashboard/web/README.md).

## Preserved SQL prototype

The original runner remains separate and requires the configured SQL Server test database, an ODBC driver, and its own dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r services/autorunner/requirements_poc_runner.txt
.\.venv\Scripts\python.exe services/autorunner/autotuner_poc_runner.py --help
```

Consult the autorunner README and database-specific setup scripts before running an experiment. The demo can clear Query Store and apply/drop indexes; starting the new API does none of those operations. Existing Compose files are prototype scaffolding and do not launch the new API.

## FR-01 collector validation

Install the backend validation package with `.\.venv\Scripts\python.exe -m pip install -e "services/collector[dev]"`. See [Target validation](TARGET_VALIDATION.md) for tests and an optional manual database connection check. The API exposes health and Test Connection endpoints. See [Target API](TARGET_API.md) for the HTTP check.
