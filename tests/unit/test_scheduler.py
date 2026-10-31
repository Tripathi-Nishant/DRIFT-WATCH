import pandas as pd

from driftwatch.scheduler import run_due_schedules
from driftwatch.storage import Store


def test_due_schedule_records_success(tmp_path):
    reference = tmp_path / "reference.csv"
    current = tmp_path / "current.csv"
    output = tmp_path / "report.json"
    pd.DataFrame({"value": [1, 2, 3]}).to_csv(reference, index=False)
    pd.DataFrame({"value": [1, 2, 4]}).to_csv(current, index=False)
    store = Store(tmp_path / "driftwatch.db")
    schedule = store.create_schedule(
        "org", "hourly", "hourly",
        config={
            "reference_path": str(reference),
            "current_path": str(current),
            "output_path": str(output),
        },
    )

    runs = run_due_schedules(store, "org")

    assert runs[0]["status"] == "SUCCEEDED"
    assert output.exists()
    assert store.list_schedule_runs("org", schedule["id"])[0]["id"] == runs[0]["id"]
