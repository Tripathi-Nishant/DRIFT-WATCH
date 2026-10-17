from driftwatch.storage import Store


def test_retraining_request_is_persisted_and_approved(tmp_path):
    store = Store(tmp_path / "dw.db")
    organization = store.create_organization("Acme")
    request = store.create_retraining_request(
        organization["id"], None, "user-1", {"severity": "HIGH"}
    )
    assert (
        store.list_retraining_requests(organization["id"])[0]["status"]
        == "PENDING_APPROVAL"
    )
    approved = store.approve_retraining_request(
        organization["id"], request["id"], "user-2"
    )
    assert approved["status"] == "APPROVED"
