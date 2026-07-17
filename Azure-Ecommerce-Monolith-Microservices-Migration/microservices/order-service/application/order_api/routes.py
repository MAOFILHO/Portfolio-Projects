from flask import jsonify, make_response, request

from . import order_api_blueprint
from .. import db
from ..models import Order, OrderItem
from ..schemas import OrderAddItemRequest
from ..validation import validate_form
from .api.UserClient import UserClient


@order_api_blueprint.route("/api/orders", methods=["GET"])
def orders():
    return jsonify([o.to_json() for o in Order.query.all()])


@order_api_blueprint.route("/api/order/add-item", methods=["POST"])
def order_add_item():
    api_key = request.headers.get("Authorization")
    response = UserClient.get_user(api_key)
    if not response:
        return make_response(jsonify({"message": "Not logged in"}), 401)

    data, error = validate_form(OrderAddItemRequest, request.form)
    if error:
        return error

    user = response["result"]
    u_id = int(user["id"])

    known_order = Order.query.filter_by(user_id=u_id, is_open=True).first()
    if known_order is None:
        known_order = Order(user_id=u_id, is_open=True)
        known_order.items.append(OrderItem(data.product_id, data.qty))
    else:
        existing = next((i for i in known_order.items if i.product_id == data.product_id), None)
        if existing:
            existing.quantity += data.qty
        else:
            known_order.items.append(OrderItem(data.product_id, data.qty))

    db.session.add(known_order)
    db.session.commit()
    return jsonify({"result": known_order.to_json()})


@order_api_blueprint.route("/api/order", methods=["GET"])
def order():
    api_key = request.headers.get("Authorization")
    response = UserClient.get_user(api_key)
    if not response:
        return make_response(jsonify({"message": "Not logged in"}), 401)

    user = response["result"]
    open_order = Order.query.filter_by(user_id=user["id"], is_open=True).first()
    if open_order is None:
        return jsonify({"message": "No order found"})
    return jsonify({"result": open_order.to_json()})


@order_api_blueprint.route("/api/order/checkout", methods=["POST"])
def checkout():
    api_key = request.headers.get("Authorization")
    response = UserClient.get_user(api_key)
    if not response:
        return make_response(jsonify({"message": "Not logged in"}), 401)

    user = response["result"]
    order_model = Order.query.filter_by(user_id=user["id"], is_open=True).first()
    if order_model is None:
        return make_response(jsonify({"message": "No open order"}), 404)

    order_model.is_open = False
    db.session.add(order_model)
    db.session.commit()
    return jsonify({"result": order_model.to_json()})
