import pandas as pd

from driftwatch import analyze


def test_analysis_detects_numeric_and_categorical_drift():
    reference = pd.DataFrame(
        {"score": [1, 2, 3, 4, 5], "plan": ["free", "free", "free", "pro", "pro"]}
    )
    current = pd.DataFrame(
        {"score": [20, 21, 22, 23, 24], "plan": ["pro", "pro", "pro", "pro", "free"]}
    )
    result = analyze(reference, current)
    assert result["summary"]["features"] == 2
    assert result["summary"]["drifted_features"] == 2
    assert result["features"][0]["name"] == "score"


def test_numeric_and_categorical_reports_include_secondary_statistics():
    reference = pd.DataFrame(
        {"score": [1, 2, 3, 4, 5], "plan": ["free", "free", "pro", "pro", "pro"]}
    )
    current = pd.DataFrame(
        {"score": [20, 21, 22, 23, 24], "plan": ["pro", "pro", "pro", "team", "team"]}
    )
    result = analyze(reference, current)
    by_name = {feature["name"]: feature for feature in result["features"]}
    assert "ks_statistic" in by_name["score"]["metrics"]
    assert "wasserstein" in by_name["score"]["metrics"]
    assert "chi_square_p_value" in by_name["plan"]["metrics"]
    assert "team" in by_name["plan"]["metrics"]["new_categories"]
