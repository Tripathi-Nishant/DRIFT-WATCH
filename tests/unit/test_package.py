import pandas as pd

import driftwatch
from driftwatch import monitor


def test_package_version_exists():
    assert driftwatch.__version__ == "0.1.0"


def test_monitor_helper_uses_client(monkeypatch):
    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def monitor(self, reference, current, **kwargs):
            return {"summary": {"decision": "IGNORE"}, "rows": (len(reference), len(current))}

    monkeypatch.setattr("driftwatch.DriftWatchClient", FakeClient)
    result = monitor(pd.DataFrame({"x": [1]}), pd.DataFrame({"x": [2]}))
    assert result["summary"]["decision"] == "IGNORE"
