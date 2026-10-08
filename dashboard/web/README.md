# Database Tuner dashboard

FR-01 now provides a target configuration form and Test Connection action. It supports Windows and SQL authentication, certificate options, ODBC driver selection, and timeouts. Passwords are masked, held only in component memory, and cleared after each test or authentication-mode change. Connection results are cleared when any field changes. Inputs are disabled during a pending test.

## Run locally

Start the Python API from the repository root:

```powershell
.\.venv\Scripts\python.exe -m autotuner_api
```

In another terminal:

```powershell
Set-Location dashboard/web
npm ci
npm run dev
```

Open the URL printed by Vite, normally http://127.0.0.1:5173. Restart Vite if it was running before the proxy configuration changed. The form starts with the project's local SQLEXPRESS instance and WideWorldImporters database. Enable **Trust server certificate** for this local demo, then click **Test connection**. The default keeps certificate verification enabled.

The frontend uses relative `/api` requests. Vite forwards these to `http://127.0.0.1:8080`; for another API port, set `$env:AUTOTUNER_API_URL = 'http://127.0.0.1:YOUR_PORT'` before starting Vite. Preview uses the same proxy. A production host must route `/api` to the backend separately.

## Checks

```powershell
npm test
npm run build
```

The tests cover request construction and safe response handling; they are not browser E2E automation. For a manual check, test the local target, change the database field and confirm the previous result disappears, and verify SQL authentication shows a masked password field. No Save action is provided yet: target persistence and selection remain pending FR-01 tasks. Test Connection does not save a target or modify database data.
