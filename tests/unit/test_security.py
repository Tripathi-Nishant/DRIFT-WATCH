from driftwatch.security import (
    hash_password,
    issue_token,
    verify_password,
    verify_token,
)


def test_passwords_and_signed_sessions():
    encoded = hash_password("correct horse")
    assert verify_password("correct horse", encoded)
    assert not verify_password("wrong", encoded)
    token = issue_token("user-1", "OWNER", "org-1", secret="test-secret")
    assert verify_token(token, secret="test-secret")["role"] == "OWNER"
    assert verify_token(token, secret="wrong") is None
