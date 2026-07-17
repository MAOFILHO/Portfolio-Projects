"""Shared schema for the monolith — one database, all domains.

This is intentional: in the AFTER (microservices) state, each of these three
models is split out into its own service with its own database. Here they
share a single SQLAlchemy metadata / single database file, which is exactly
the "Shared Persistence" coupling the migration removes.
"""
from datetime import datetime, timezone

from flask_login import UserMixin
from passlib.hash import sha256_crypt

from . import db


def _utcnow():
    return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(255), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    first_name = db.Column(db.String(255), nullable=True)
    last_name = db.Column(db.String(255), nullable=True)
    password = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    api_key = db.Column(db.String(255), unique=True, nullable=True)
    date_added = db.Column(db.DateTime, default=_utcnow)
    date_updated = db.Column(db.DateTime, onupdate=_utcnow)

    def encode_api_key(self):
        self.api_key = sha256_crypt.hash(self.username + str(_utcnow()))

    def encode_password(self):
        self.password = sha256_crypt.hash(self.password)

    def verify_password(self, raw_password: str) -> bool:
        return sha256_crypt.verify(raw_password, self.password)

    def to_json(self):
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "is_admin": self.is_admin,
        }


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True, nullable=False)
    slug = db.Column(db.String(255), unique=True, nullable=False)
    price = db.Column(db.Integer, nullable=False)
    image = db.Column(db.String(255), nullable=True)
    date_added = db.Column(db.DateTime, default=_utcnow)
    date_updated = db.Column(db.DateTime, onupdate=_utcnow)

    def to_json(self):
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "price": self.price,
            "image": self.image,
        }


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
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
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    date_added = db.Column(db.DateTime, default=_utcnow)

    def to_json(self):
        return {"product_id": self.product_id, "quantity": self.quantity}
