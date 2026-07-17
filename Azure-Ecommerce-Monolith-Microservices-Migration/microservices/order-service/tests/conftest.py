import os
import sys
from pathlib import Path

import pytest

SERVICE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

os.environ.setdefault("RUN_MODE", "local")
os.environ.setdefault("FLASK_ENV", "development")
os.environ.setdefault("SECRET_KEY", "test-secret")
TEST_DB_PATH = "instance/test_order.sqlite3"
os.environ["ORDER_DB_PATH"] = TEST_DB_PATH


@pytest.fixture
def app():
    from application import create_app, db

    flask_app = create_app("development")
    with flask_app.app_context():
        db.drop_all()
        db.create_all()
        yield flask_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture(scope="session", autouse=True)
def _cleanup_test_db():
    """Removes only this test suite's own db file (and its SQLite sidecar
    files), never the whole instance/ directory — that directory can also
    hold the real app's live database if `make run` is active alongside
    `make test`, and rmtree-ing it out from under a running process breaks
    it (SQLite can no longer create journal/WAL files once the directory is
    gone, surfacing as a confusing 'attempt to write a readonly database').
    This was a real bug, found by deleting a live dev database this way."""
    yield
    base = SERVICE_ROOT / TEST_DB_PATH
    for suffix in ("", "-journal", "-wal", "-shm"):
        Path(f"{base}{suffix}").unlink(missing_ok=True)
