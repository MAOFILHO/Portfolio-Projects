from flask import jsonify, make_response, request

from . import product_api_blueprint
from .. import db
from ..models import Product
from ..schemas import ProductCreateRequest
from ..validation import validate_form


@product_api_blueprint.route("/api/products", methods=["GET"])
def products():
    return jsonify({"results": [p.to_json() for p in Product.query.all()]})


@product_api_blueprint.route("/api/product/create", methods=["POST"])
def post_create():
    data, error = validate_form(ProductCreateRequest, request.form)
    if error:
        return error

    item = Product(name=data.name, slug=data.slug, image=data.image, price=data.price)
    db.session.add(item)
    db.session.commit()
    return jsonify({"message": "Product added", "product": item.to_json()})


@product_api_blueprint.route("/api/product/<slug>", methods=["GET"])
def product(slug):
    item = Product.query.filter_by(slug=slug).first()
    if item is None:
        return make_response(jsonify({"message": "Cannot find product"}), 404)
    return jsonify({"result": item.to_json()})


@product_api_blueprint.route("/api/product/<slug>", methods=["DELETE"])
def delete_product(slug):
    """Lets scripts/benchmark.py clean up the throwaway products it creates
    to measure create_product latency, instead of leaving hundreds of
    'bench-*' rows permanently cluttering the Shop catalog."""
    item = Product.query.filter_by(slug=slug).first()
    if item is None:
        return make_response(jsonify({"message": "Cannot find product"}), 404)
    db.session.delete(item)
    db.session.commit()
    return jsonify({"message": "Product deleted"})
