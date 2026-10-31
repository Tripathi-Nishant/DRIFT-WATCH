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
