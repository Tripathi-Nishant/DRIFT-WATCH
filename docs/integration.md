# Integrating a model with DriftWatch

DriftWatch is model-agnostic. The model project owns training and inference;
DriftWatch receives a baseline window, a current window, predictions, and
optional delayed labels.

## Install and analyze locally

```bash
python -m pip install "driftwatch @ git+https://github.com/Tripathi-Nishant/DRIFT-WATCH.git"
```

```python
import pandas as pd
from driftwatch import DriftWatchClient

client = DriftWatchClient("http://localhost:8765", token="YOUR_DASHBOARD_JWT")
report = client.analyze(
    pd.read_csv("reference.csv"),
    pd.read_csv("current.csv"),
    model_name="fraud-classifier",
    model_type="classification",
    predictions=model.predict(current),
    labels=current_labels,
)
print(report["summary"]["decision"])
```

For a production job, create an ingestion key in **Models & projects** and use
it instead of a human JWT:

```python
from driftwatch import DriftWatchClient

client = DriftWatchClient(
    "https://monitor.example.com",
    api_key="dw_live_your_key",
)
client.analyze(reference_records, current_records, model_name="ranking-v2")
```

The reference and current records must use the same feature names and the same
preprocessing pipeline. If labels are unavailable, DriftWatch still reports
data and prediction drift but cannot calculate current model quality.

## API contract

The running service exposes an OpenAPI-compatible description at:

```text
GET /openapi.json
```

The API also exposes `/metrics`, `/healthz`, and `/readyz` for deployment and
monitoring systems. Keep API keys server-side, rotate them, and never commit
them to a repository.
