from driftwatch.server import _validate_access_request
from driftwatch.storage import Store


def test_access_request_validation_normalizes_safe_input():
    assert _validate_access_request(
        {"email": " User@Example.com ", "organization": " Acme ", "use_case": " Drift "}
    ) == ("user@example.com", "Acme", "Drift")


def test_access_request_validation_rejects_invalid_input():
    assert _validate_access_request({"email": "not-an-email", "organization": "Acme"}) is None
    assert _validate_access_request({"email": "a@b.com", "organization": ""}) is None
    assert _validate_access_request([]) is None


def test_access_request_deduplicates_pending_email(tmp_path):
    store = Store(tmp_path / "driftwatch.db")
    first = store.create_access_request("user@example.com", "Acme", "First")
    second = store.create_access_request("USER@example.com", "Other", "Second")
    assert second["id"] == first["id"]
    assert second["organization"] == "Acme"
