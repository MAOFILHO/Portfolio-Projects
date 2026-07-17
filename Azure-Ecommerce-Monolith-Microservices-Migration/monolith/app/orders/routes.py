"""Order domain — identical *external* API surface to microservices/order-service,
but note the internal difference: here the order logic queries the User table
directly in the same database/session (Shared Persistence). In the microservices
version, order-service has no access to the user database at all and must call
user-service over HTTP instead. That contrast is the point of this monolith."""
from flask import Blueprint, jsonify, make_response, request
from flask_login import login_required

from .. import db
from ..models import Order, OrderItem, User
from ..schemas import OrderAddItemRequest
from ..validation import validate_form

orders_blueprint = Blueprint("orders", __name__, url_prefix="/api")


def _user_from_api_key():
    api_key = request.headers.get("Authorization", "").replace("Basic ", "", 1)
    if not api_key:
        return None
    return User.query.filter_by(api_key=api_key).first()


@orders_blueprint.get("/orders")
def list_orders():
    return jsonify([o.to_json() for o in Order.query.all()])


@orders_blueprint.post("/order/add-item")
def add_item():
    user = _user_from_api_key()
    if not user:
        return make_response(jsonify({"message": "Not logged in"}), 401)

    data, error = validate_form(OrderAddItemRequest, request.form)
    if error:
        return error

    order = Order.query.filter_by(user_id=user.id, is_open=True).first()
    if order is None:
        order = Order(user_id=user.id, is_open=True)
        order.items.append(OrderItem(product_id=data.product_id, quantity=data.qty))
    else:
        existing = next((i for i in order.items if i.product_id == data.product_id), None)
        if existing:
            existing.quantity += data.qty
        else:
            order.items.append(OrderItem(product_id=data.product_id, quantity=data.qty))

    db.session.add(order)
    db.session.commit()
    return jsonify({"result": order.to_json()})


@orders_blueprint.get("/order")
def get_open_order():
    user = _user_from_api_key()
    if not user:
        return make_response(jsonify({"message": "Not logged in"}), 401)

    order = Order.query.filter_by(user_id=user.id, is_open=True).first()
    if order is None:
        return jsonify({"message": "No order found"})
    return jsonify({"result": order.to_json()})


@orders_blueprint.post("/order/checkout")
def checkout():
    user = _user_from_api_key()
    if not user:
        return make_response(jsonify({"message": "Not logged in"}), 401)

    order = Order.query.filter_by(user_id=user.id, is_open=True).first()
    if order is None:
        return make_response(jsonify({"message": "No open order"}), 404)

    order.is_open = False
    db.session.add(order)
    db.session.commit()
    return jsonify({"result": order.to_json()})
