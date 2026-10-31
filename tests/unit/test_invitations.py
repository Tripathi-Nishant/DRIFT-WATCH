import hashlib

from driftwatch.security import hash_password
from driftwatch.storage import Store


def test_approved_access_request_returns_one_time_invitation(tmp_path):
    store = Store(tmp_path / "driftwatch.db")
    request = store.create_access_request("user@example.com", "Acme", "Monitoring")
    reviewed = store.review_access_request(request["id"], "APPROVED", "owner")
    assert reviewed["invitation_token"].startswith("dw_invite_")

    accepted = store.accept_access_invitation(
        hashlib.sha256(reviewed["invitation_token"].encode()).hexdigest(),
        hash_password("strong-password"),
    )
    assert accepted["user"]["email"] == "user@example.com"
    assert store.accept_access_invitation(
        hashlib.sha256(reviewed["invitation_token"].encode()).hexdigest(),
        hash_password("strong-password"),
    ) is None
