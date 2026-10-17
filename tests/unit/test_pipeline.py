import pandas as pd

from driftwatch import Monitor, ReferenceProfile


def test_monitor_adds_decision_quality_and_recommendation():
    reference = pd.DataFrame(
        {"age": [20, 21, 22, 23, 24], "plan": ["free", "free", "pro", "pro", "pro"]}
    )
    current = pd.DataFrame(
        {"age": [45, 46, 47, 48, 49], "plan": ["pro", "pro", "pro", "team", "team"]}
    )
    result = Monitor.from_reference(reference, model_name="checkout").run(current)
    assert result.severity in {"HIGH", "CRITICAL"}
    assert result.decision == "ACT"
    assert result.report["summary"]["recommendation"]


def test_reference_profile_round_trip(tmp_path):
    profile_path = tmp_path / "reference.profile.json"
    profile = ReferenceProfile.from_dataframe(
        pd.DataFrame({"x": [1, 2, 3], "kind": ["a", "b", "a"]})
    )
    profile.save(profile_path)
    loaded = ReferenceProfile.load(profile_path)
    assert loaded.rows == 3
    assert loaded.schema["x"]["kind"] == "numeric"


def test_html_report_contains_explanations_and_secondary_statistics(tmp_path):
    reference = pd.DataFrame({"x": [1, 2, 3, 4, 5]})
    current = pd.DataFrame({"x": [10, 11, 12, 13, 14]})
    output = tmp_path / "report.html"
    Monitor.from_reference(reference).run(current).save_html(output)
    content = output.read_text(encoding="utf-8")
    assert "Possible contributing factor" in content
    assert "ks_statistic" in content
