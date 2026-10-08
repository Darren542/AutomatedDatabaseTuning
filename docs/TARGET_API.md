# Test Connection API

FR-01 now exposes `POST /api/v1/targets/test-connection`. It validates the submitted configuration and tests database access; it does not save a target, return a reusable approval token, or change database data.

## Start

From the repository root, install both local packages together so pip resolves the monorepo collector dependency:

```powershell
.\.venv\Scripts\python.exe -m pip install -e "services/collector[dev]" -e "services/api[dev]"
.\.venv\Scripts\python.exe -m autotuner_api
```

If the API was already running, stop it with Ctrl+C and restart to load the new routes. Open http://127.0.0.1:8080/docs to inspect the request schema.

## Verify the local demo

In a second PowerShell terminal:

```powershell
$targetRequest = @{
    name = 'Local demo'
    server = 'localhost\SQLEXPRESS'
    database = 'WideWorldImporters'
    authentication = 'windows'
    trust_server_certificate = $true
} | ConvertTo-Json

Invoke-RestMethod -Uri 'http://127.0.0.1:8080/api/v1/targets/test-connection' `
    -Method Post -ContentType 'application/json' -Body $targetRequest
```

Expected result: `connected` is `True`, `code` is `connected`, and the message confirms database access. This uses the local instance/certificate settings verified in the previous task. Encryption remains enabled. Windows authentication uses the API process identity.

## Request and response contract

Required fields: `name`, `server`, `database`. Optional fields: `authentication` (`windows` or `sql`), `driver` (Microsoft ODBC Driver 17 or 18), `encrypt`, `trust_server_certificate`, and integer `connection_timeout_seconds` / `query_timeout_seconds` from 1 to 60. Defaults match `TargetConfiguration`.

For SQL authentication supply a nested `credentials` object with `username` and `password`. Windows authentication must omit credentials or set them to null. Passwords are request-only and never returned. Use the request body, not query parameters, for credentials. Target metadata and validation results are not credential storage.

HTTP 200 means the connection test completed, not that the connection succeeded. Check `connected` and `code`; authentication failure, timeout, and connection failure return `connected=false` with the collector's safe message. HTTP 422 means the request is malformed or its configuration is invalid, and no connection is attempted. Unknown fields and type coercions such as `"false"` for a boolean are rejected.

Both typed and malformed input errors are sanitized; responses do not echo submitted bodies or arbitrary field names. The 422 shape is `{"detail":"..."}`. A successful response is:

```json
{"connected":true,"code":"connected","message":"Connection to the selected database succeeded."}
```

This endpoint remains a local development API without user authentication. Save/list/select endpoints, protected credential persistence, and UI integration remain separate FR-01 tasks. There is no in-memory saved-target workaround.

## Automated checks

```powershell
.\.venv\Scripts\python.exe -m pytest services/api/tests services/collector/tests --import-mode=importlib
```

Tests cover HTTP-to-service mapping, Windows/SQL authentication, invalid settings, malformed JSON, credential non-disclosure, and failed connection results. They use a test service; the manual command above verifies the real SQL Server path.
