from app.models import Order, OrderItem, Product, User


def test_password_hash_roundtrip(app):
    user = User(username="alice", email="alice@example.com", password="secret123")
    user.encode_password()
    assert user.password != "secret123"
    assert user.verify_password("secret123") is True
    assert user.verify_password("wrong") is False


def test_api_key_is_unique_per_call(app):
    user = User(username="bob", email="bob@example.com", password="x")
    user.encode_password()
    user.encode_api_key()
    first_key = user.api_key
    user.encode_api_key()
    assert user.api_key != first_key


def test_product_to_json_shape(app):
    product = Product(name="Widget", slug="widget", price=1999)
    data = product.to_json()
    assert data["name"] == "Widget"
    assert data["price"] == 1999


def test_order_aggregates_items(app, client):
    from app import db

    with app.app_context():
        order = Order(user_id=1, is_open=True)
        order.items.append(OrderItem(product_id=1, quantity=2))
        order.items.append(OrderItem(product_id=2, quantity=1))
        db.session.add(order)
        db.session.commit()

        data = order.to_json()
        assert data["is_open"] is True
        assert len(data["items"]) == 2
        assert {i["product_id"] for i in data["items"]} == {1, 2}
