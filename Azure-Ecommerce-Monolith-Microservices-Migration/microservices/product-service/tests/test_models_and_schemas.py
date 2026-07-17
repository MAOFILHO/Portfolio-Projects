import pytest
from pydantic import ValidationError

from application.models import Product
from application.schemas import ProductCreateRequest


def test_product_to_json_shape(app):
    product = Product(name="Widget", slug="widget", price=1999)
    data = product.to_json()
    assert data["name"] == "Widget"
    assert data["price"] == 1999


def test_product_create_rejects_non_positive_price():
    with pytest.raises(ValidationError):
        ProductCreateRequest(name="Widget", slug="widget", price=-5)


def test_product_create_accepts_valid_payload():
    req = ProductCreateRequest(name="Widget", slug="widget", price=1999)
    assert req.slug == "widget"
