import json

from driftwatch.retraining import approve_request, create_request


def test_retraining_requires_explicit_approval(tmp_path):
    path = tmp_path / "request.json"
    create_request(
        {
            "summary": {
                "model": "fraud",
                "severity": "HIGH",
                "decision": "ACT",
                "recommendation": "RETRAIN",
            }
        },
        path,
    )
    assert json.loads(path.read_text())["status"] == "PENDING_APPROVAL"
    approved = approve_request(path, "engineer@example.com")
    assert approved["status"] == "APPROVED"
    assert approved["approved_by"] == "engineer@example.com"
