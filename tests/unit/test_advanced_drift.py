import pandas as pd

from driftwatch import Monitor, analyze


def test_multivariate_drift_is_available_for_large_windows():
    reference = pd.DataFrame({"x": range(100), "y": range(100)})
    current = pd.DataFrame({"x": range(100, 200), "y": range(100, 200)})
    result = analyze(reference, current)
    assert result["multivariate"]["available"] is True
    assert result["multivariate"]["auc"] >= 0.5


def test_subgroup_drift_is_reported():
    reference = pd.DataFrame(
        {"segment": ["a"] * 50 + ["b"] * 50, "value": list(range(100))}
    )
    current = pd.DataFrame(
        {
            "segment": ["a"] * 50 + ["b"] * 50,
            "value": list(range(50)) + list(range(100, 150)),
        }
    )
    result = Monitor.from_reference(reference).run(current, group_by="segment")
    assert set(result.report["subgroups"]) == {"a", "b"}
