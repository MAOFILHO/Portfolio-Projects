import pytest
from pydantic import ValidationError

from application.models import User
from application.schemas import LoginRequest, RegisterRequest


def test_password_hash_roundtrip(app):
    user = User(username="alice", email="alice@example.com", password="secret123")
    user.encode_password()
    assert user.password != "secret123"
    assert user.verify_password("secret123") is True
    assert user.verify_password("wrong") is False


def test_register_request_rejects_invalid_email():
    with pytest.raises(ValidationError):
        RegisterRequest(username="alice", email="not-an-email", password="secret123")


def test_login_request_requires_password():
    with pytest.raises(ValidationError):
        LoginRequest(username="alice")
