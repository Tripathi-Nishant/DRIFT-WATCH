import pandas as pd

from driftwatch import Monitor


def test_custom_task_returns_generic_prediction_diagnostics():
    result = Monitor.from_reference(
        pd.DataFrame({"embedding_1": [0.1, 0.2], "embedding_2": [0.3, 0.4]}),
        model_type="anomaly_detection",
    ).run(
        pd.DataFrame({"embedding_1": [0.8, 0.9], "embedding_2": [0.7, 0.6]}),
        predictions=[0.1, 0.9],
        labels=[0, 1],
    )
    performance = result.report["performance"]
    assert performance["task_agnostic"] is True
    assert "accuracy" not in performance
    assert result.report["summary"]["task"] == "anomaly_detection"
