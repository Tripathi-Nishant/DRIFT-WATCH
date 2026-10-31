# Run DriftWatch

## Fastest local start

From the repository root in PowerShell:

```powershell
cd C:\Users\HP\Desktop\DRIFTWATCH

# Build the dashboard when frontend files changed
npm run build --prefix dashboard

# Start the API and dashboard
$env:DRIFTWATCH_ENV = "development"
$env:DRIFTWATCH_WEB_ROOT = "C:\Users\HP\Desktop\DRIFTWATCH\dashboard\dist"
.\.venv\Scripts\python.exe -m driftwatch.cli serve --host 127.0.0.1 --port 8765
```

Open <http://127.0.0.1:8765>.

In another PowerShell window, verify the service:

```powershell
Invoke-WebRequest http://127.0.0.1:8765/healthz -UseBasicParsing
Invoke-WebRequest http://127.0.0.1:8765/readyz -UseBasicParsing
```

Expected status codes are `200`. The local server uses the configured
`DRIFTWATCH_DATABASE_URL` when present; otherwise it uses SQLite at
`.driftwatch/driftwatch.db`.

## First use

1. Select **Create an account** in the dashboard.
2. Register an organization and password.
3. Sign in.
4. Open **Run analysis** and submit reference/current JSON data.
5. Review the report, trends, alerts, and audit history.

## Run with Docker Compose

Use this for PostgreSQL-backed production-like development:

```powershell
cd C:\Users\HP\Desktop\DRIFTWATCH
Copy-Item .env.example .env
# Edit .env and replace every placeholder secret.
docker compose up -d --build
docker compose ps
Invoke-WebRequest http://127.0.0.1:8765/healthz -UseBasicParsing
Invoke-WebRequest http://127.0.0.1:8765/readyz -UseBasicParsing
```

If persisted schedules are enabled, set `DRIFTWATCH_WORKER_ORG` in `.env`.
Compose will then start the separate `driftwatch-worker` service.

Stop the stack:

```powershell
docker compose down
```

Add `-v` only when intentionally deleting local PostgreSQL volumes.

## Useful commands

```powershell
# Backend checks
.\.venv\Scripts\python.exe -m ruff check src tests
.\.venv\Scripts\python.exe -m pytest -q

# Dashboard checks
npm run build --prefix dashboard
npm run test:e2e --prefix dashboard

# API load smoke test against a running server
.\.venv\Scripts\python.exe tools\load_test.py --url http://127.0.0.1:8765/healthz --requests 200 --workers 8
```

## Configuration

Copy `.env.example` to `.env` for deployment settings. Never commit `.env`,
database files, API keys, Stripe secrets, SMTP passwords, Sentry DSNs, or
OpenTelemetry credentials.
