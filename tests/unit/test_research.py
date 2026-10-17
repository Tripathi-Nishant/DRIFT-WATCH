from driftwatch.research import run_suite


def test_research_suite_records_clean_and_shifted_scenarios(tmp_path):
    result = run_suite(tmp_path / "results.json", seeds=[42])
    assert result["clean_false_alerts"] == 0
    assert result["shifted_actions"] == 1
