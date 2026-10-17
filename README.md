# DriftWatch

Open-source machine-learning monitoring for detecting data drift, model quality degradation, and operational risk.

DriftWatch provides a Python analysis library, an HTTP ingestion API, a React dashboard, PostgreSQL persistence, audit trails, retraining workflows, and Docker deployment in one self-hostable product.

> **Status:** early production candidate. Core workflows are implemented, but teams should complete their own security, capacity, backup, and provider validation before a high-stakes production rollout.

## Highlights

- Statistical drift and data-quality metrics for tabular data
- Prediction and feedback ingestion for delayed-label monitoring
- Decision layer for review, alert, and retraining recommendations
- JWT authentication, roles, projects, API keys, and audit events
- PostgreSQL-backed deployment with migration support
- Retraining request and approval history
- Dashboard for monitoring reports and operational workflows
- Docker Compose quick start and CI checks

## Quick start with Docker

Requirements: Docker Desktop with Compose v2.

```powershell
Copy-Item .env.example .env
# Edit .env and replace both placeholder secrets.
docker compose up -d --build
```

Open <http://localhost:8765>. Check service status with:

```powershell
docker compose ps
curl http://localhost:8765/healthz
curl http://localhost:8765/readyz
```

## Local development

DriftWatch requires Python 3.12. Node.js 22 is required to build and test the dashboard.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,server]"
pytest
```

Start the development server:

```powershell
driftwatch serve
```

The default local store is `.driftwatch/driftwatch.db`. Set `DRIFTWATCH_DB` to use another SQLite file, or set `DRIFTWATCH_DATABASE_URL` for PostgreSQL.

## Repository layout

```text
src/driftwatch/   Core library, API, security, storage, metrics, and workflows
dashboard/        React/Vite dashboard and browser tests
tests/             Unit and integration tests
migrations/       PostgreSQL schema migrations
docs/              Deployment and capability documentation
bench/             Research and comparison experiments
tools/             Migration and load-test utilities
```

## Documentation

- [Production deployment](docs/production.md)
- [PostgreSQL setup](docs/postgresql.md)
- [Capabilities](docs/capabilities.md)
- [Contributing](CONTRIBUTING.md)
- [Security policy](SECURITY.md)

## License

DriftWatch is released under the [MIT License](LICENSE).
