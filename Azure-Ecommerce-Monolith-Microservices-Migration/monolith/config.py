"""Environment-driven configuration for the monolith.

RUN_MODE=local -> SQLite file under monolith/instance/
RUN_MODE=azure -> Azure Database for MySQL (connection info from .env, populated by infra/provision.py)
"""
import os
from pathlib import Path
import ssl
from urllib.parse import quote_plus

BASE_DIR = Path(__file__).resolve().parent
RUN_MODE = os.environ.get("RUN_MODE", "local")


def _sqlite_uri() -> str:
    db_path = os.environ.get("MONOLITH_DB_PATH", "instance/monolith.sqlite3")
    abs_path = BASE_DIR / db_path if not Path(db_path).is_absolute() else Path(db_path)
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{abs_path}"


def _mysql_uri() -> str:
    host = os.environ["AZURE_MYSQL_HOST"]
    port = os.environ.get("AZURE_MYSQL_PORT", "3306")
    user = quote_plus(os.environ["AZURE_MYSQL_ADMIN_USER"])
    # generate_mysql_password() in infra/provision.py includes URI-reserved
    # characters (@ $ % ^ etc.) — quote_plus is required or the URL parser
    # misreads part of the password as the host. Caught for real: an
    # un-encoded '@' in the password broke the connection with "Name or
    # service not known" pointing at a garbled hostname.
    password = quote_plus(os.environ["AZURE_MYSQL_ADMIN_PASSWORD"])
    # No ?ssl_mode=REQUIRED here — that's a mysql-connector-python/mysqlclient
    # param name, not PyMySQL's. Caught for real running this live: PyMySQL's
    # connect() raised "TypeError: unexpected keyword argument 'ssl_mode'"
    # because SQLAlchemy passes every URI query param straight through as a
    # DBAPI connect() kwarg. SSL is instead requested via connect_args below,
    # in the form PyMySQL actually accepts.
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/monolith_db"


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = _mysql_uri() if RUN_MODE == "azure" else _sqlite_uri()
    if RUN_MODE == "azure":
        # Azure Database for MySQL Flexible Server enforces TLS server-side
        # regardless of client config; this just tells PyMySQL to actually
        # negotiate SSL (an empty dict = use SSL with the default context).
        SQLALCHEMY_ENGINE_OPTIONS = {"connect_args": {"ssl": ssl.create_default_context()}}
    UPLOAD_FOLDER = "application/static/images"


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


CONFIG_BY_NAME = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
}
