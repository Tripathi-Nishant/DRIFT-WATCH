from driftwatch.storage import Store


def test_store_persists_models_runs_predictions_and_feedback(tmp_path):
    store = Store(tmp_path / "driftwatch.db")
    model = store.create_model("fraud", model_type="classification")
    assert store.list_models()[0]["name"] == "fraud"
    report = {"summary": {"severity": "NORMAL", "decision": "IGNORE"}}
    run = store.record_run(report, model["id"])
    assert store.list_runs()[0]["id"] == run["id"]
    ids = store.add_predictions(
        model["id"], [{"prediction": 0.8, "features": {"amount": 10}}]
    )
    assert store.add_feedback(ids[0], 1)
    alert = store.record_alert(run["id"], "webhook", "skipped", "not configured")
    assert store.list_alerts()[0]["id"] == alert["id"]


def test_store_filters_run_history(tmp_path):
    store = Store(tmp_path / "driftwatch.db")
    first = store.record_run(
        {"summary": {"severity": "HIGH", "decision": "ACT"}},
        model_id="model-a",
    )
    store.record_run(
        {"summary": {"severity": "NORMAL", "decision": "IGNORE"}},
        model_id="model-b",
    )
    filtered = store.list_runs(model_id="model-a", severity="HIGH", decision="ACT")
    assert [item["id"] for item in filtered] == [first["id"]]


def test_store_persists_platform_configuration(tmp_path):
    store = Store(tmp_path / "driftwatch.db")
    dataset = store.create_dataset_version(
        "org", "checkout-reference", "v2", "reference", 10, 3, "abc123"
    )
    schedule = store.create_schedule("org", "Hourly checkout", "hourly")
    rule = store.create_alert_rule("org", "Critical drift", "CRITICAL", "webhook")
    assert store.list_dataset_versions("org")[0]["id"] == dataset["id"]
    assert store.list_schedules("org")[0]["id"] == schedule["id"]
    assert store.list_alert_rules("org")[0]["id"] == rule["id"]


def test_alert_rule_can_suppress_unmatched_severity(tmp_path):
    from driftwatch.alerts import AlertDispatcher

    store = Store(tmp_path / "driftwatch.db")
    store.create_alert_rule("org", "Critical only", "CRITICAL", "webhook")
    run = store.record_run(
        {"summary": {"severity": "HIGH", "decision": "ACT", "model": "checkout"}},
        organization_id="org",
    )
    result = AlertDispatcher(store).dispatch(run)
    assert result["status"] == "skipped"
    assert "No enabled rule" in result["detail"]


def test_alert_rule_enforces_metric_threshold(tmp_path):
    from driftwatch.alerts import AlertDispatcher

    store = Store(tmp_path / "driftwatch.db")
    store.create_alert_rule(
        "org", "Severe drift only", "HIGH", "webhook",
        threshold=0.8, metric="drift_rate",
    )
    run = store.record_run(
        {
            "summary": {
                "severity": "HIGH", "decision": "ACT", "model": "checkout",
                "drift_rate": 0.4,
            }
        },
        organization_id="org",
    )
    result = AlertDispatcher(store).dispatch(run)
    assert result["status"] == "skipped"
    assert "thresholds" in result["detail"]


def test_store_persists_research_evidence(tmp_path):
    store = Store(tmp_path / "driftwatch.db")
    item = store.record_research_run(
        "org", "synthetic", [1, 7], {"clean_false_alerts": 0}
    )
    saved = store.list_research_runs("org")
    assert saved[0]["id"] == item["id"]
    assert saved[0]["seeds"] == [1, 7]
    assert saved[0]["result"]["clean_false_alerts"] == 0
