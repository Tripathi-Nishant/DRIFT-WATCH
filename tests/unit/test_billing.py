from driftwatch.storage import Store


def test_billing_account_persists(tmp_path):
    store = Store(tmp_path / "driftwatch.db")
    saved = store.save_billing_account("org", "cus_1", "sub_1", "pro", "active")
    assert store.get_billing_account("org") == saved
