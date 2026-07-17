from flask import jsonify, make_response, request
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy.exc import IntegrityError

from . import user_api_blueprint
from .. import db, login_manager
from ..models import User
from ..schemas import RegisterRequest, LoginRequest
from ..validation import validate_form


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@login_manager.request_loader
def load_user_from_request(req):
    api_key = req.headers.get("Authorization", "").replace("Basic ", "", 1)
    if api_key:
        return User.query.filter_by(api_key=api_key).first()
    return None


@user_api_blueprint.route("/api/users", methods=["GET"])
def get_users():
    return jsonify([u.to_json() for u in User.query.all()])


@user_api_blueprint.route("/api/user/create", methods=["POST"])
def post_register():
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


@user_api_blueprint.route("/api/user/login", methods=["POST"])
def post_login():
    data, error = validate_form(LoginRequest, request.form)
    if error:
        return error

    user = User.query.filter_by(username=data.username).first()
    if user and user.verify_password(data.password):
        user.encode_api_key()
        db.session.commit()
        login_user(user)
        return make_response(jsonify({"message": "Logged in", "api_key": user.api_key}))
    return make_response(jsonify({"message": "Not logged in"}), 401)


@user_api_blueprint.route("/api/user/logout", methods=["POST"])
def post_logout():
    if current_user.is_authenticated:
        logout_user()
        return make_response(jsonify({"message": "You are logged out"}))
    return make_response(jsonify({"message": "You are not logged in"}))


@user_api_blueprint.route("/api/user/<username>/exists", methods=["GET"])
def get_username(username):
    if User.query.filter_by(username=username).first() is not None:
        return jsonify({"result": True})
    return make_response(jsonify({"message": "Cannot find username"}), 404)


@user_api_blueprint.route("/api/user", methods=["GET"])
@login_required
def get_user():
    return make_response(jsonify({"result": current_user.to_json()}))
