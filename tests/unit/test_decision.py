import pandas as pd

from driftwatch import DecisionConfig, Monitor


def test_decision_layer_exposes_trace_and_estimated_impact():
    reference = pd.DataFrame({"score": range(100)})
    current = pd.DataFrame({"score": range(300, 400)})
    result = Monitor.from_reference(
        reference,
        decision_config={
            "period_volume": 20_000,
            "cost_false_negative": 50_000,
            "action_cost": 150_000,
        },
    ).run(current)
    assert result.decision == "ACT"
    assert result.report["summary"]["rule_trace"]
    assert result.report["summary"]["impact_estimate"]["label"] == "estimate"
    assert result.report["features"][0]["explanation"].startswith(
        "Possible contributing factor"
    )


def test_small_windows_are_low_confidence():
    result = Monitor.from_reference(
        pd.DataFrame({"x": [1, 2, 3]}),
        decision_config=DecisionConfig(min_samples=30),
    ).run(pd.DataFrame({"x": [1, 2, 3]}))
    assert result.report["summary"]["low_confidence"] is True


def test_prediction_drift_is_reported_when_prediction_baseline_is_available():
    monitor = Monitor.from_reference(
        pd.DataFrame({"x": range(100)}),
        reference_predictions=[0.1] * 100,
    )
    result = monitor.run(
        pd.DataFrame({"x": range(100)}),
        predictions=[0.9] * 100,
    )
    assert "prediction_drift" in result.report
