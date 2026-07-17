"""product-service — owns the product catalog and its own database."""
import os

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

db = SQLAlchemy()
migrate = Migrate()


def create_app(config_name: str | None = None) -> Flask:
    from config import CONFIG_BY_NAME

    config_name = config_name or os.environ.get("FLASK_ENV", "development")
    app = Flask(__name__)
    app.config.from_object(CONFIG_BY_NAME[config_name])

    db.init_app(app)
    migrate.init_app(app, db)

    with app.app_context():
        from . import models  # noqa: F401
        from .product_api import product_api_blueprint

        app.register_blueprint(product_api_blueprint)

        # db.create_all() runs regardless of RUN_MODE — see monolith/app/__init__.py
        # for why (migrations/ has no actual Alembic revisions, so gating
        # this to local-only left Azure MySQL with no schema at all).
        db.create_all()
        from .seed import seed_products_if_empty

        seed_products_if_empty()

        @app.get("/health")
        def health():
            return {"status": "ok", "service": "product-service"}

        return app
