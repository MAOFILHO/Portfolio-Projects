"""Catalog domain — identical API surface to microservices/product-service."""
from flask import Blueprint, jsonify, make_response, request

from .. import db
from ..models import Product
from ..schemas import ProductCreateRequest
from ..validation import validate_form

catalog_blueprint = Blueprint("catalog", __name__, url_prefix="/api")


@catalog_blueprint.get("/products")
def list_products():
    return jsonify({"results": [p.to_json() for p in Product.query.all()]})


@catalog_blueprint.post("/product/create")
def create_product():
    data, error = validate_form(ProductCreateRequest, request.form)
    if error:
        return error

    product = Product(name=data.name, slug=data.slug, image=data.image, price=data.price)
    db.session.add(product)
    db.session.commit()
    return jsonify({"message": "Product added", "product": product.to_json()})


@catalog_blueprint.get("/product/<slug>")
def get_product(slug):
    product = Product.query.filter_by(slug=slug).first()
    if product is None:
        return make_response(jsonify({"message": "Cannot find product"}), 404)
    return jsonify({"result": product.to_json()})


@catalog_blueprint.delete("/product/<slug>")
def delete_product(slug):
    """Lets scripts/benchmark.py clean up the throwaway products it creates
    to measure create_product latency, instead of leaving hundreds of
    'bench-*' rows permanently cluttering the Shop catalog."""
    product = Product.query.filter_by(slug=slug).first()
    if product is None:
        return make_response(jsonify({"message": "Cannot find product"}), 404)
    db.session.delete(product)
    db.session.commit()
    return jsonify({"message": "Product deleted"})
