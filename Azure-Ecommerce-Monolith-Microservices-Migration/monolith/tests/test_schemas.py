import pytest
from pydantic import ValidationError

from app.schemas import LoginRequest, OrderAddItemRequest, ProductCreateRequest, RegisterRequest


def test_register_request_rejects_short_username():
    with pytest.raises(ValidationError):
        RegisterRequest(username="ab", email="a@example.com", password="secret123")


def test_register_request_rejects_invalid_email():
    with pytest.raises(ValidationError):
        RegisterRequest(username="alice", email="not-an-email", password="secret123")


def test_register_request_rejects_short_password():
    with pytest.raises(ValidationError):
        RegisterRequest(username="alice", email="a@example.com", password="123")


def test_register_request_accepts_valid_payload():
    req = RegisterRequest(username="alice", email="a@example.com", password="secret123")
    assert req.username == "alice"


def test_login_request_requires_both_fields():
    with pytest.raises(ValidationError):
        LoginRequest(username="alice")


def test_product_create_rejects_non_positive_price():
    with pytest.raises(ValidationError):
        ProductCreateRequest(name="Widget", slug="widget", price=0)


def test_product_create_accepts_valid_payload():
    req = ProductCreateRequest(name="Widget", slug="widget", price=1999)
    assert req.price == 1999


def test_order_add_item_rejects_non_positive_qty():
    with pytest.raises(ValidationError):
        OrderAddItemRequest(product_id=1, qty=0)
