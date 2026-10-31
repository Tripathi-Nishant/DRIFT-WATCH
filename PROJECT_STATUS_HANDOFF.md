# DriftWatch — Project Status and Handoff

Last updated: 31 October 2026  
Repository: `https://github.com/Tripathi-Nishant/DRIFT-WATCH`  
Current branch: `main`  
Latest feature commit: `5b707a7`

This document is the authoritative handoff for the DriftWatch project. It is
written so that a new developer or AI agent can understand what exists, how the
parts connect, how to run it, what has been verified, and what remains before a
larger production launch.

## 1. Product summary

DriftWatch is a self-hostable machine-learning monitoring platform inspired by
products such as Evidently, but designed as a small, understandable, open-source
Beta for students, colleges, and small ML teams.

The product compares a reference/baseline dataset with a current/production
dataset. It measures data drift, data quality, prediction drift, and optional
model quality. It then produces an explainable decision such as:

- `MONITOR`
- `INVESTIGATE`
- `ACT`
- `IGNORE`

The main differentiator is the decision and workflow layer. DriftWatch does not
only show statistical changes; it explains severity, confidence, reasons,
estimated impact, alert status, and whether a human-approved retraining request
should be created.

The Student Placement Predictor is only an optional test client. It is located
under `examples/placement-predictor-demo/` and is not part of the DriftWatch
core product, package, Docker runtime, or dashboard dependency graph.

## 2. Current implementation status

The core Beta product is implemented and working.

Verified on the latest development run:

- Python tests: `29 passed, 1 skipped`
- PostgreSQL integration test: passed against the local Docker database
- Ruff lint: passed
- React/Vite production build: passed
- Playwright browser tests: `3 passed`
- Python wheel build: passed
- Docker production image build: passed
- Docker PostgreSQL service: healthy
- `/healthz`: returns `PostgresStore`
- `/readyz`: returns ready
- `/openapi.json`: returns the API contract
- Repository is synchronized with GitHub

The one normally skipped test is the PostgreSQL integration test when
`DRIFTWATCH_DATABASE_URL` is not configured. In CI, PostgreSQL is started as a
GitHub Actions service.

## 3. Architecture

```text
Model project / batch job
        |
        | Python library, DriftWatchClient, or HTTP API
        v
DriftWatch analysis pipeline
        |
        +--> statistical metrics
        +--> data-quality checks
        +--> prediction-quality metrics
        +--> optional text/image/LLM/RAG metrics
        +--> decision layer
        v
Report + persisted monitoring run
        |
        +--> React dashboard
        +--> alert dispatcher
        +--> audit trail
        +--> retraining request workflow
```

Runtime choices:

- SQLite is the default local backend.
- PostgreSQL is selected with `DRIFTWATCH_DATABASE_URL`.
- Docker Compose runs the dashboard/API and PostgreSQL.
- Redis is an optional distributed ingestion adapter.
- Qdrant is an optional vector-store adapter.
- Heavy embedding and vision dependencies are optional.

## 4. Repository structure

```text
src/driftwatch/
  advanced_metrics.py   Ranking, LLM, RAG, and embedding-related metrics
  alerts.py             Webhook/email alert delivery and retries
  client.py             Dependency-light Python integration client
  cli.py                `driftwatch` command-line interface
  decision.py           Severity, confidence, impact, and action decisions
  metrics.py            Core metric families and metric catalog
  monitor.py            Low-level tabular drift analysis
  multimodal.py         Text and image baseline analysis
  observability.py      Prometheus metrics and structured event logging
  openapi.py             OpenAPI-compatible API description
  pipeline.py            Monitor, MonitorResult, performance, report assembly
  postgres_store.py     PostgreSQL persistence backend
  production.py         Embeddings, Gemini, privacy, limits, rate limiting
  queue.py              Local and Redis ingestion queues
  report.py             Self-contained HTML report rendering
  research.py           Research benchmark and confidence interval runner
  retraining.py         File-based retraining helpers
  scheduler.py          Repeated monitoring helpers
  security.py           Password hashing, JWTs, and API key generation
  server.py             HTTP API and dashboard server
  storage.py            SQLite persistence backend
  vector_store.py       Qdrant REST adapter

dashboard/
  src/main.jsx          React dashboard screens and report components
  src/styles.css        Dashboard styling
  src/multimodal.css    Multimodal report styling
  tests/                Playwright browser tests

tests/
  unit/                 Core unit tests
  integration/          PostgreSQL integration test
  e2e/                  Browser-test notes

docs/
  integration.md        Generic model integration guide
  production.md         Production deployment checklist
  postgresql.md         PostgreSQL setup
  capabilities.md       Implemented capability boundary
  aws-small.md          Low-cost AWS deployment guide

examples/placement-predictor-demo/
  Optional test client and dataset. Not part of the core DriftWatch product.

migrations/              Database migration files
tools/                   Backup, restore, load-test, and utility scripts
Dockerfile               Multi-stage dashboard/API production image
docker-compose.yml       Local API + PostgreSQL stack
.github/workflows/ci.yml GitHub Actions test, build, audit, and Trivy workflow
pyproject.toml           Package metadata, dependencies, and CLI entry points
START_HERE.md             Demo and local usage runbook
README.md                Public project overview
```

## 5. Implemented monitoring capabilities

### Tabular monitoring

- Numerical drift using PSI, KS, Wasserstein, mean, and variance changes
- Categorical frequency and chi-square changes
- New and missing categories
- Schema and data-type differences
- Missing-value rates
- Duplicate rows
- Constant columns
- Percentile-based outlier rates
- Joint distribution drift using a domain classifier AUC
- Basic subgroup/segment drift

### Model-quality monitoring

Classification support includes:

- Accuracy
- Precision
- Recall
- F1
- ROC-AUC
- Confusion matrix
- ROC curve data
- Precision/recall curve data
- Prediction distribution

Regression support includes:

- MAE
- RMSE
- R²
- MAPE
- Residual mean
- Residual spread
- P95 absolute error

Quality metrics require predictions and actual labels. If labels are delayed or
unavailable, DriftWatch still reports data drift and prediction drift, but it
cannot claim current model accuracy.

### Text, image, ranking, LLM, and RAG capabilities

Baseline support exists for:

- Text empty rate, uniqueness, character length, word length, and distribution
  changes
- TF-IDF centroid semantic shift
- Image shape, channel, pixel, histogram, brightness, contrast, clipping, and
  edge-energy metrics
- Optional Sentence Transformer embeddings
- Optional CLIP-style image embeddings
- Ranking metrics such as NDCG@k, MRR@k, precision@k, and hit-rate@k
- Transparent token-overlap LLM relevance and groundedness metrics
- RAG retrieval hit rate and context precision
- Optional governed Gemini LLM judge integration
- Project-specific metric plugins via `register_metric`, with report output and
  API catalog discovery
- Deterministic reference-profile fingerprints for tying runs to a reference
  schema and row shape

These multimodal and LLM capabilities are baselines or adapters. They are not
equivalent to a calibrated production computer-vision model or a fully
validated LLM judge.

## 6. Decision and workflow features

The decision layer is a DriftWatch-specific differentiator. It combines drift,
data quality, performance, sample size, and multivariate evidence to produce:

- Severity
- Confidence
- Low-confidence warnings
- Human-readable reasons
- Rule trace with values and thresholds
- Estimated impact
- Recommended action

Workflow features include:

- Organization and project separation
- JWT login sessions
- Roles including owner, admin, ML engineer, and viewer
- API keys for model-job ingestion
- Audit events
- Retraining request creation
- Human approval of retraining requests
- Retraining approval history
- Webhook and email alert delivery
- Alert retries and delivery status
- Dashboard alert history

## 7. Dashboard screens

The current React dashboard includes:

- Login and registration
- Overview/workspace health
- Latest decision summary
- Historical drift and quality trend chart
- Composite model-health score ring combining drift and quality evidence
- Ranked risk-hotspot view for the most affected features
- Cross-window drift heatmap showing feature intensity across recent runs
- Latest-versus-previous window comparison for drift, quality, and decision
- Recent monitoring runs
- CSV upload and analysis form
- Full report page
- Feature-level drift chart and table
- Data-quality findings
- Decision rule trace
- Classification visualizations
- Regression residual diagnostics
- Text/image/ranking/LLM/RAG report sections when supplied
- Models and projects page
- API-key creation
- Retraining page and approval history
- Alerts page with delivery status
- Audit-log page
- Operations control plane for dataset versions, schedules, alert rules, and
  multi-model comparison
- Research Lab for seeded benchmark execution, confidence intervals, experiment
  history, and JSON evidence downloads
- Four-line SDK integration with environment configuration and copy-ready
  onboarding snippet
- JSON report download

## 8. Python package and integration

The package is not yet published to PyPI. The current installation method is:

```bash
python -m pip install "driftwatch @ git+https://github.com/Tripathi-Nishant/DRIFT-WATCH.git"
```

Local editable development installation:

```powershell
python -m pip install -e ".[dev,server]"
```

Direct library use:

```python
from driftwatch import Monitor

monitor = Monitor.from_reference(
    reference_df,
    model_name="my-model",
    model_type="classification",
)
result = monitor.run(
    current_df,
    predictions=model.predict(current_df),
    labels=current_labels,
)
result.save_html("driftwatch-report.html")
```

Service integration with the new client:

```python
from driftwatch import DriftWatchClient

client = DriftWatchClient(
    "http://localhost:8765",
    api_key="INGESTION_KEY_CREATED_IN_DASHBOARD",
)

report = client.analyze(
    reference_df,
    current_df,
    model_name="my-model",
    model_type="classification",
    predictions=model.predict(current_df),
    labels=current_labels,
)

print(report["summary"]["decision"])
```

Other model projects should provide the same contract:

```text
reference features + current features
optional predictions + actual labels
                    |
                    v
              DriftWatch API
                    |
                    v
          dashboard report and decision
```

Reference and current data must use compatible feature names and the same
preprocessing pipeline. DriftWatch does not inspect arbitrary model internals
automatically.

## 9. HTTP API

The running service exposes:

```text
GET  /healthz
GET  /readyz
GET  /metrics
GET  /openapi.json
GET  /api/v1/metrics

POST /api/v1/auth/register
POST /api/v1/auth/login
POST /api/analyze
POST /api/ingest/predictions
POST /api/ingest/feedback
POST /api/models
POST /api/v1/projects
POST /api/v1/api-keys
POST /api/v1/retraining
POST /api/v1/retraining/{id}/approve

GET  /api/runs
GET  /api/models
GET  /api/alerts
GET  /api/v1/projects
GET  /api/v1/audit
GET  /api/v1/retraining
```

Use JWT authorization for dashboard and administrative operations. Use
`X-DriftWatch-Key` for production ingestion jobs. Keep API keys server-side,
rotate them, and never commit them to source control.

## 10. Running the project

### Docker Compose

Create `.env` from `.env.example`, set strong local values, and run:

```powershell
docker compose up -d --build
docker compose ps
curl.exe http://localhost:8765/healthz
curl.exe http://localhost:8765/readyz
```

Open:

```text
http://localhost:8765
```

If PowerShell variables are preferred:

```powershell
$env:POSTGRES_PASSWORD = "driftwatch-local-password"
$env:DRIFTWATCH_SECRET_KEY = "local-only-secret-change-me"
docker compose up -d --build
```

### Local checks

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check src tests tools
npm run build --prefix dashboard
npm run test:e2e --prefix dashboard
```

For the local Windows PostgreSQL integration test, IPv4 avoids a common
`localhost`/IPv6 resolution issue:

```powershell
$env:DRIFTWATCH_DATABASE_URL = "postgresql://driftwatch:driftwatch-local-password@127.0.0.1:5432/driftwatch"
.\.venv\Scripts\python.exe -m pytest tests/integration/test_postgres.py -q
```

## 11. CI/CD and security checks

`.github/workflows/ci.yml` currently runs:

- Python 3.12 setup
- Dependency installation
- PostgreSQL service container
- Unit tests
- PostgreSQL integration test
- `pip-audit`
- Ruff
- Docker build
- Trivy HIGH/CRITICAL image scan with unfixed vulnerabilities ignored
- Dashboard npm install
- Dashboard production build
- Playwright browser tests

The Dockerfile uses a multi-stage Node/Python build and applies available Debian
security upgrades before installing the runtime package.

## 12. What remains

### Product work remaining

- Publish a stable release to PyPI.
- Add a versioned SDK release and typed API models.
- Add full OpenAPI request/response schemas and generated clients.
- Add threshold-aware alert-rule evaluation for metric-specific policies; current
  rules enforce severity and channel/destination selection.
- Add first-class project/model selection to the dashboard analysis form.
- Add interactive drill-down from heatmap cells directly into a selected run.
- Add dashboard controls that use the API's model, project, severity, and date
  range filters.
- Add schedule execution worker supervision and run history links for each
  configured schedule.
- Add dataset upload/version promotion workflows beyond metadata registration.
- Add paper-specific statistical tests and matched Evidently benchmark reporting.

### Provider and research work remaining

- Validate Sentence Transformer models on real production datasets.
- Validate CLIP/vision embeddings and add calibrated computer-vision quality
  models for specific use cases.
- Validate Gemini/LLM judges with real credentials, prompt versions, cost
  limits, PII policy, and a calibration dataset.
- Compare matched DriftWatch metrics against Evidently on larger public datasets.
- Expand benchmark datasets, confidence intervals, and published reports.
- Add drift threshold calibration by domain and sample size.

### Infrastructure and operations remaining

- Deploy behind TLS/reverse proxy with secure headers and domain configuration.
- Use managed or properly supervised Redis for high-volume workers.
- Deploy and validate Qdrant for vector workloads if needed.
- Add queue workers and scheduled monitoring jobs for distributed operation.
- Run production-sized load tests and horizontal scaling tests.
- Configure Prometheus/Grafana or an equivalent metrics, tracing, and alert
  platform.
- Configure external encrypted backups and perform restore drills.
- Add CI dependency pinning, dependency scanning, container scanning policy, and
  release automation.
- Add secrets management rather than environment variables alone.

## 13. Honest product boundary

DriftWatch is a working, production-shaped Beta suitable for college projects,
student teams, prototypes, and small startup deployments. It is substantially
more than a login demo: it includes a monitoring engine, API, database layer,
dashboard reports, decision workflow, alert history, auditability, and Docker
deployment.

It is not yet full Evidently-level breadth or large-scale enterprise maturity.
The remaining gap is primarily validated providers, operational infrastructure,
calibrated research comparisons, release packaging, and scale testing—not the
basic monitoring workflow.

## 14. Instructions for the next AI/developer

When continuing this project:

1. Read this file first.
2. Preserve `examples/placement-predictor-demo/` as an optional client only.
3. Do not add the placement model as a dependency of `src/driftwatch/`.
4. Run tests and Ruff before changing architecture.
5. Use Docker Compose with explicit environment variables for PostgreSQL checks.
6. Do not commit `.env`, credentials, API keys, database files, or model secrets.
7. Check `docs/capabilities.md` before claiming a feature is production-ready.
8. Update this handoff document whenever a major capability or limitation
   changes.
9. Treat the decision layer, human approval workflow, audit trail, and model-
   agnostic integration client as important DriftWatch differentiators.
10. Be honest about baseline versus calibrated/provider-backed multimodal and
    LLM capabilities.
