"""Monolith application factory.

This is the BEFORE state of the migration story: one Flask process, one
database, one codebase that owns auth, catalog, and order logic together.
Compare with microservices/ where the same business capabilities are split
into three independently deployable Flask services with their own databases.
"""
import os

from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()


def create_app(config_name: str | None = None) -> Flask:
    from config import CONFIG_BY_NAME

    config_name = config_name or os.environ.get("FLASK_ENV", "development")
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config.from_object(CONFIG_BY_NAME[config_name])

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "You must log in to access this page."

    with app.app_context():
        from . import models  # noqa: F401 (registers models with SQLAlchemy)

        from .auth.routes import auth_blueprint
        from .catalog.routes import catalog_blueprint
        from .orders.routes import orders_blueprint

        app.register_blueprint(auth_blueprint)
        app.register_blueprint(catalog_blueprint)
        app.register_blueprint(orders_blueprint)

        # db.create_all() runs regardless of RUN_MODE. The migrations/
        # folder exists (Flask-Migrate is wired in) but has no actual Alembic
        # revision files in it — caught for real deploying to Azure MySQL for
        # the first time: `flask db upgrade` would be a no-op, so nothing
        # ever created the schema there, and every request 500'd with
        # "Table 'monolith_db.product' doesn't exist". create_all() is
        # idempotent (only creates missing tables), so it's safe to always
        # run rather than gating it to local-only.
        db.create_all()
        from .seed import seed_products_if_empty

        seed_products_if_empty()

        @login_manager.user_loader
        def load_user(user_id):
            return models.User.query.get(int(user_id))

        @app.get("/health")
        def health():
            return {"status": "ok", "service": "monolith"}

        return app
