"""Auth domain — identical API surface to microservices/user-service, so the
FastAPI BFF can call either backend with the same client code."""
from flask import Blueprint, jsonify, make_response, request
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy.exc import IntegrityError

from .. import db
from ..models import User
from ..schemas import RegisterRequest, LoginRequest
from ..validation import validate_form

auth_blueprint = Blueprint("auth", __name__, url_prefix="/api")


@auth_blueprint.get("/users")
def get_users():
    return jsonify([u.to_json() for u in User.query.all()])


@auth_blueprint.post("/user/create")
def register():
    data, error = validate_form(RegisterRequest, request.form)
    if error:
        return error

    user = User(
        username=data.username,
        email=data.email,
        first_name=data.first_name,
        last_name=data.last_name,
        password=data.password,
    )
    user.encode_password()
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return make_response(
            jsonify({"message": "Username or email is already taken"}), 409
        )
    return jsonify({"message": "User added", "result": user.to_json()})


@auth_blueprint.post("/user/login")
def login():
    data, error = validate_form(LoginRequest, request.form)
    if error:
        return error

    user = User.query.filter_by(username=data.username).first()
    if user and user.verify_password(data.password):
        user.encode_api_key()
        db.session.commit()
        login_user(user)
        return jsonify({"message": "Logged in", "api_key": user.api_key})
    return make_response(jsonify({"message": "Not logged in"}), 401)


@auth_blueprint.post("/user/logout")
def logout():
    if current_user.is_authenticated:
        logout_user()
        return jsonify({"message": "You are logged out"})
    return jsonify({"message": "You are not logged in"})


@auth_blueprint.get("/user/<username>/exists")
def username_exists(username):
    exists = User.query.filter_by(username=username).first() is not None
    if exists:
        return jsonify({"result": True})
    return make_response(jsonify({"message": "Cannot find username"}), 404)


@auth_blueprint.get("/user")
@login_required
def get_current_user():
    return jsonify({"result": current_user.to_json()})
