# DriftWatch: Start Here

DriftWatch is a small-team ML observability platform. It compares a reference
dataset with a current production batch, measures drift and data quality,
checks optional model performance, and produces an explainable decision such as
`MONITOR`, `INVESTIGATE`, or `ACT`.

The repository includes a Student Placement Predictor as the main case study.

## 1. Requirements

- Windows 10/11
- Docker Desktop with the Linux engine enabled
- Python 3.11 or newer
- Git
- Node.js 22 only if changing the dashboard

## 2. Start the full product with Docker

Open PowerShell:

```powershell
cd C:\Users\HP\Desktop\DRIFTWATCH

$env:POSTGRES_PASSWORD = "driftwatch-local-password"
$env:DRIFTWATCH_SECRET_KEY = "change-this-demo-secret"

docker compose up -d --build
docker compose ps
curl.exe http://localhost:8765/healthz
curl.exe http://localhost:8765/readyz
```

Expected responses:

```json
{"status": "ok", "backend": "PostgresStore"}
{"status": "ready"}
```

Open the dashboard at <http://localhost:8765> and create a workspace account.

For a new terminal, set the two environment variables again, or create a local
`.env` file from `.env.example`. Never commit real passwords or API keys.

## 3. Run the first dashboard analysis

1. Sign in.
2. Open **Run analysis**.
3. Upload a reference CSV and a current CSV, or edit the sample JSON.
4. Select `Classification` or `Regression`.
5. Click **Analyze data**.
6. Review the full report.

The report includes:

- Drift rate and affected features
- Quality score and findings
- Feature-level explanations
- Decision and confidence
- Rule trace
- Model performance when labels are supplied
- Historical trends across runs
- Multimodal metrics when supplied
- Downloadable JSON

## 4. Install the Python package and CLI

Until a unique PyPI name is selected, install the repository version:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,server]"
```

Generate an offline report from any tabular CSV pair:

```powershell
driftwatch run `
  --reference reference.csv `
  --current current.csv `
  --model-type classification `
  --out report.html
```

Open `report.html` in a browser.

## 5. Placement Predictor case study

The case study is in `Placement-Predictor-main`.

Run the prediction app:

```powershell
cd C:\Users\HP\Desktop\DRIFTWATCH\Placement-Predictor-main
..\.venv\Scripts\python.exe -m streamlit run app/app.py
```

Run the reproducible DriftWatch demonstration:

```powershell
..\.venv\Scripts\python.exe integrations/make_drift_demo.py
```

This creates:

```text
data/demo/reference.csv
data/demo/current.csv
data/demo/current_labels.csv
```

Submit the demo batch. Use the same email and password you used to register in
the DriftWatch dashboard:

```powershell
..\.venv\Scripts\python.exe integrations/driftwatch_monitor.py `
  --email "your-registered-email" `
  --password "your-password" `
  --reference data/demo/reference.csv `
  --current data/demo/current.csv `
  --current-labels data/demo/current_labels.csv
```

Return to the dashboard and open **Full report**. The generated demo batch is
intentionally shifted and should produce visible drift and an action-oriented
decision.

To run it repeatedly on a small server or laptop:

```powershell
..\.venv\Scripts\python.exe integrations/watch_driftwatch.py `
  --email "your-registered-email" `
  --password "your-password" `
  --interval 3600
```

The connector expects processed model-ready columns from `X_prepared.csv`. Do
not compare the raw placement CSV directly with processed data because the
schemas and encodings are different.

## 6. Optional embeddings and alerts

The free baseline works without these dependencies. Enable them only when
needed:

```powershell
python -m pip install "driftwatch[production]"
$env:DRIFTWATCH_EMBEDDING_MODEL = "all-MiniLM-L6-v2"
$env:DRIFTWATCH_IMAGE_EMBEDDING_MODEL = "openai/clip-vit-base-patch32"
```

Configure a Slack/Discord-compatible webhook:

```powershell
$env:DRIFTWATCH_WEBHOOK_URL = "https://your-webhook-url"
```

Email alerts are optional and use the `DRIFTWATCH_SMTP_*` variables documented
in `.env.example`. Alerts are sent only for `HIGH` and `CRITICAL` runs and use
retry attempts.

## 7. Local development and validation

```powershell
python -m pip install -e ".[dev,server]"
python -m pytest -q
python -m ruff check src tests tools
npm run build --prefix dashboard
```

Dashboard browser tests:

```powershell
$env:PATH = "C:\Users\HP\Desktop\DRIFTWATCH\.venv\Scripts;" + $env:PATH
npm run test:e2e --prefix dashboard
```

## 8. Showcase script

Use this order in a presentation:

1. Explain the production problem: a model can become unreliable after data changes.
2. Show the placement model predicting student placement.
3. Explain reference data versus current production data.
4. Generate the intentionally shifted demo batch.
5. Submit it to DriftWatch.
6. Show drifted features and the feature chart.
7. Show the quality score and decision rule trace.
8. Open the historical trend view.
9. Show the retraining approval workflow.
10. Download the report and show the CLI command.

## 9. Troubleshooting

### Port 8765 is unavailable

```powershell
docker compose ps
docker compose logs driftwatch
```

### Docker says environment variables are missing

Set `POSTGRES_PASSWORD` and `DRIFTWATCH_SECRET_KEY` in the current PowerShell
session before running `docker compose up`.

### The report shows 0% drift

Confirm that reference and current are different files. Comparing the same file
to itself correctly produces zero drift. Run `make_drift_demo.py` for a visible
demonstration.

### Placement model file is missing

Run the model-training notebook or confirm this file exists:

```text
Placement-Predictor-main/models/placement_model.pkl
```

### Dashboard changes do not appear

Rebuild the image:

```powershell
docker compose up -d --build
```

Then hard-refresh the browser with `Ctrl+F5`.

## 10. Current project boundary

DriftWatch is production-shaped and suitable for college projects, prototypes,
and small startup teams. Tabular monitoring is the most complete path. Text and
image monitoring are available through local baselines and optional embedding
providers. Large-scale distributed operation, managed secrets, and high-stakes
model validation still require deployment-specific work.
