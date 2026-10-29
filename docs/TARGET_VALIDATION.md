# Target configuration and connection validation

FR-01 backend foundation lives in `collector.targets` and `collector.connection_validation`. It can be called by the API later without importing HTTP types into the collector.

## Contract

`TargetConfiguration` is immutable metadata: display name, server/instance (including a SQL Server endpoint such as `localhost,1433`), database, authentication mode, selected ODBC driver, TLS flags, and login/query timeouts. Required text, authentication mode, boolean types, driver selection, and timeout bounds are validated at construction. Invalid input raises `TargetConfigurationError` with a message that does not echo input values.

Authentication modes are `windows` (default) and `sql`. Windows authentication uses the identity running the Python process, not a future browser user's Windows identity. SQL authentication takes a separate `SqlCredentials` object. Credentials are transient: password whitespace is preserved, object repr hides both fields, and neither the target metadata nor the validation result contains credentials. Do not serialize credentials with dataclass utilities or return them from an API. Protected credential storage and HTTP input/output schemas are subsequent tasks.

`ConnectionValidationService.validate(target, credentials=None)` returns a `ConnectionValidationResult` with `code`, `message`, and a computed `connected` property. It does not save a target or mark it active. A successful result applies only to that invocation; any future save operation must validate the configuration being saved.

Result codes: `connected`, `invalid_configuration`, `driver_unavailable`, `authentication_failed`, `timeout`, `connection_failed`, `database_unavailable`, and `validation_failed`. Driver diagnostics are deliberately not returned or logged. Some server permission/database failures share driver SQLSTATE values, so messages give troubleshooting guidance without claiming an exact cause.

Validation opens a connection, sets the query timeout, and issues a parameterized read-only probe that checks the current database against the requested database. Cursor and connection are explicitly closed on success and failure. It performs no DDL, workload execution, collection, Query Store changes, or persistence. Login and query timeouts are separate ODBC limits, not an absolute wall-clock limit for the whole operation.

Microsoft ODBC Driver 17 and 18 are supported. Encryption is enabled and certificate trust bypass is disabled by default. For a local instance with a self-signed certificate, explicitly opt into `trust_server_certificate=True` when appropriate; do not silently retry with weaker TLS settings.

## Install and test

From the repository root in PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pip install -e "services/collector[dev]"
.\.venv\Scripts\python.exe -m pytest services/collector/tests
```

Unit tests inject a fake connector and do not need a SQL Server instance. The actual driver and a reachable target are needed for the following manual check.

```powershell
.\.venv\Scripts\python.exe
```

For this project's local prototype, the verified instance is `localhost\SQLEXPRESS` and the database is `WideWorldImporters`. The prototype explicitly trusts its local server certificate. The example below matches those settings; for other targets, use the exact instance and certificate policy from your working connection.

```python
from collector.targets import TargetConfiguration, SqlCredentials
from collector.connection_validation import ConnectionValidationService

target = TargetConfiguration(
    name="Local demo",
    server=r"localhost\SQLEXPRESS",
    database="WideWorldImporters",
    trust_server_certificate=True,  # Explicit opt-in for this local demo instance.
)
result = ConnectionValidationService().validate(target)
print(result.code.value, result.message)
```

`localhost` addresses the default instance and is not interchangeable with `localhost\SQLEXPRESS`. This local check succeeded with certificate trust enabled; with it disabled, the connection failed. Encryption remains enabled. The model default still verifies certificates, so the local opt-in does not change other targets.

For SQL authentication, construct the target with `authentication="sql"` and supply `SqlCredentials(username=input("SQL username: "), password=getpass("SQL password: "))`, importing `getpass` from `getpass` first. Do not paste credentials into source files or shell commands. No configuration is automatically read from the prototype's `.env` by this service.

## Remaining FR-01 work

The Test Connection endpoint is implemented; see [Target API](TARGET_API.md). Save/list/select API endpoints, save/revalidation rules, credential references, persistence, target selector, form, and Test Connection UI are still to be implemented. Query Store and collector-specific permission checks belong to FR-02; this validation only establishes access to the selected database.

Implementation references: [Microsoft ODBC options](https://learn.microsoft.com/en-us/sql/connect/odbc/dsn-connection-string-attribute) and [pyodbc connection lifecycle and query timeout](https://github.com/mkleehammer/pyodbc/wiki/Connection).


## Elevated-permission connections

Excessive ALTER/DDL permissions are a warning rather than a collector-readiness failure. Connectivity and all required telemetry reads must still pass. Target setup displays an acknowledgement checkbox before Save target is enabled. Changing the configuration or retesting clears the acknowledgement.

Saving revalidates the actual server-side credential reference. If that account has elevated permissions, POST /api/v1/targets requires `acknowledge_excessive_permissions: true`; otherwise it returns HTTP 428. This also handles a restricted test account paired with a more privileged saved reference. Acknowledgement never bypasses failed connectivity or missing read permissions. It is not persisted as a database field, and no SQL migration is required. Saved-target access tests continue to report the permission warning.
