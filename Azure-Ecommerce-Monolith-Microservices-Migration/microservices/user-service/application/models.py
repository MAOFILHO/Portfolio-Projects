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
