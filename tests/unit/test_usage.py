from driftwatch.storage import Store


def test_usage_summary_reports_counts_and_remaining_quota(tmp_path, monkeypatch):
    monkeypatch.setenv("DRIFTWATCH_QUOTA_RUNS", "1")
    store = Store(tmp_path / "driftwatch.db")
    store.record_run(
        {"summary": {"severity": "NORMAL", "decision": "IGNORE"}},
        organization_id="org",
    )
    summary = store.usage_summary("org")
    assert summary["usage"]["runs"] == 1
    assert summary["remaining"]["runs"] == 0
    assert "runs" in summary["exceeded"]
