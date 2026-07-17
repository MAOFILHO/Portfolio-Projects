"""RUN_MODE=local -> SQLite file. RUN_MODE=azure -> Azure Database for MySQL (own logical DB)."""
import os
from pathlib import Path
import ssl
from urllib.parse import quote_plus

BASE_DIR = Path(__file__).resolve().parent
RUN_MODE = os.environ.get("RUN_MODE", "local")


def _sqlite_uri() -> str:
    db_path = os.environ.get("USER_DB_PATH", "instance/user.sqlite3")
    abs_path = BASE_DIR / db_path if not Path(db_path).is_absolute() else Path(db_path)
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{abs_path}"


def _mysql_uri() -> str:
    host = os.environ["AZURE_MYSQL_HOST"]
    port = os.environ.get("AZURE_MYSQL_PORT", "3306")
    user = quote_plus(os.environ["AZURE_MYSQL_ADMIN_USER"])
    # generate_mysql_password() in infra/provision.py includes URI-reserved
    # characters (@ $ % ^ etc.) — quote_plus is required or the URL parser
    # misreads part of the password as the host.
    password = quote_plus(os.environ["AZURE_MYSQL_ADMIN_PASSWORD"])
    # No ?ssl_mode=REQUIRED — that's a mysql-connector-python/mysqlclient
    # param name, not PyMySQL's; SQLAlchemy passes URI query params straight
    # through as DBAPI connect() kwargs, which raised a real TypeError.
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/user_db"


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = _mysql_uri() if RUN_MODE == "azure" else _sqlite_uri()
    if RUN_MODE == "azure":
        SQLALCHEMY_ENGINE_OPTIONS = {"connect_args": {"ssl": ssl.create_default_context()}}


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


CONFIG_BY_NAME = {"development": DevelopmentConfig, "production": ProductionConfig}
