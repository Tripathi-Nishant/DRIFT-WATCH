# Production deployment checklist

## Providers

Install the production extra and configure a real embedding model when semantic
meaning is required:

```powershell
python -m pip install -e ".[production]"
$env:DRIFTWATCH_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
```

`semantic_text_metrics(..., provider=embedding_provider())` uses the configured
Sentence Transformers model. The default remains the deterministic TF-IDF
baseline. LLM and vision judges are explicit provider interfaces; DriftWatch
does not silently send customer prompts or images to a third party.

## PostgreSQL and health checks

Set `DRIFTWATCH_DATABASE_URL` and run the service behind a reverse proxy. The
container compose file starts PostgreSQL with a health check and exposes:

- `/healthz`: process health
- `/readyz`: database readiness
- `/api/v1/metrics`: metric catalog

The integration test runs when `DRIFTWATCH_DATABASE_URL` is present:

```powershell
$env:DRIFTWATCH_DATABASE_URL = "postgresql://driftwatch:password@localhost:5432/driftwatch"
python -m pytest tests/integration/test_postgres.py -q
```

## Security and privacy

- Use a strong `DRIFTWATCH_SECRET_KEY` in the deployment environment.
- Restrict `DRIFTWATCH_ALLOWED_ORIGINS` to the dashboard origin.
- Set `DRIFTWATCH_MAX_BODY_BYTES` to the largest accepted payload.
- Use API keys only for ingestion and rotate/revoke them.
- Audit payloads with `production.redacted`; raw prompts, answers, labels,
  tokens, emails, and contexts should not be placed in logs.
- Terminate TLS at the reverse proxy and keep PostgreSQL private.

## Load testing

Run the dependency-free smoke test against a deployed health endpoint:

```powershell
python tools/load_test.py --url https://monitor.example.com/healthz --requests 1000 --workers 32
```

Record p50/p95 latency and error rate for the target deployment. This script is
an acceptance harness, not a substitute for capacity testing with production
payloads and a managed database.

## Backups, rollback, and connection pooling

The PostgreSQL backend uses `psycopg_pool` with configurable bounds:

```powershell
$env:DRIFTWATCH_DB_POOL_MIN = "2"
$env:DRIFTWATCH_DB_POOL_MAX = "20"
```

The container entrypoint applies ordered files in `migrations/` and records
applied versions in `driftwatch_schema_migrations`. Take a custom-format backup
before migrations or releases:

```powershell
python tools/backup_postgres.py --output backups/driftwatch-$(Get-Date -Format yyyyMMddHHmmss).dump
```

Restore to a maintenance database with:

```powershell
python tools/restore_postgres.py backups/driftwatch-20260101000000.dump
```

Keep backups outside the application host, encrypt them at rest, test restores
regularly, and use a release migration that is backward compatible with the
previous application version. A migration is not considered deployable until it
has passed against a production-sized database snapshot.
