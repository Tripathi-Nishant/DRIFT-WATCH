# PostgreSQL deployment

The local SQLite backend remains the default. For the server deployment, install
the optional backend and set a PostgreSQL URL:

```powershell
python -m pip install "driftwatch[server]"
$env:DRIFTWATCH_DATABASE_URL = "postgresql://driftwatch:password@localhost:5432/driftwatch"
```

The backend uses the same storage interface and creates tenant, user, project,
model, run, alert, and audit tables on startup. Keep migrations in deployment
automation before applying destructive schema changes.
