import pandas as pd

from driftwatch import Monitor, metric_catalog
from driftwatch.metrics import data_quality_metrics, text_metrics


def test_metric_catalog_exposes_monitoring_families():
    families = {item["family"] for item in metric_catalog()}
    assert {"drift", "quality", "text", "performance", "tests"} <= families


def test_quality_and_text_metrics_are_included_in_monitor_result():
    reference = pd.DataFrame(
        {"message": ["short text", "another sentence"], "value": [1, 2]}
    )
    current = pd.DataFrame(
        {"message": ["a much longer sentence here", ""], "value": [2, 4]}
    )
    result = Monitor.from_reference(reference).run(current).to_dict()
    assert "quality_metrics" in result
    assert "message" in result["text_metrics"]
    assert result["text_metrics"]["message"]["current_empty_rate"] == 0.5
    assert result["tests"]


def test_standalone_quality_metrics_detect_schema_change():
    report = data_quality_metrics(
        pd.DataFrame({"a": [1, 2], "b": ["x", "y"]}),
        pd.DataFrame({"a": [1, 2], "c": [3, 4]}),
    )
    assert report["missing_columns"] == ["b"]
    assert report["new_columns"] == ["c"]


def test_text_metric_reports_length_shift():
    report = text_metrics(
        pd.Series(["a", "b"]),
        pd.Series(["a very long sentence", "another long sentence"]),
    )
    assert report["current_mean_characters"] > report["reference_mean_characters"]
