from datetime import datetime, timezone

from . import db


def _utcnow():
    return datetime.now(timezone.utc)


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)  # no FK — user table lives in another service
    items = db.relationship("OrderItem", backref="order", cascade="all, delete-orphan")
    is_open = db.Column(db.Boolean, default=True)
    date_added = db.Column(db.DateTime, default=_utcnow)
    date_updated = db.Column(db.DateTime, onupdate=_utcnow)

    def to_json(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "is_open": self.is_open,
            "items": [i.to_json() for i in self.items],
        }


class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False)
    product_id = db.Column(db.Integer, nullable=False)  # no FK — product table lives elsewhere
    quantity = db.Column(db.Integer, default=1)
    date_added = db.Column(db.DateTime, default=_utcnow)

    def __init__(self, product_id, quantity):
        self.product_id = product_id
        self.quantity = quantity

    def to_json(self):
        return {"product_id": self.product_id, "quantity": self.quantity}
