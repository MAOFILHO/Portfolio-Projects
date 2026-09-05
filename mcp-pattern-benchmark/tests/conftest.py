"""Throwaway Postgres for backend API tests.

Starts one postgres:16 container for the whole test session (via the docker
CLI, already a project dependency for Docker Compose — no testcontainers
needed for six endpoints), applies backend/schema.sql, and resets it between
tests so each test starts from an empty schema.
"""

import subprocess
import time
import uuid
from pathlib import Path

import psycopg2
import pytest

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "backend" / "schema.sql"


@pytest.fixture(scope="session")
def postgres_url():
    name = f"tickets-test-pg-{uuid.uuid4().hex[:8]}"
    subprocess.run(
        [
            "docker", "run", "-d", "--rm", "--name", name,
            "-e", "POSTGRES_PASSWORD=postgres",
            "-p", "127.0.0.1::5432",
            "postgres:16-alpine",
        ],
        check=True, capture_output=True,
    )
    try:
        port = subprocess.run(
            ["docker", "port", name, "5432/tcp"],
            check=True, capture_output=True, text=True,
        ).stdout.strip().rsplit(":", 1)[-1]
        url = f"postgresql://postgres:postgres@localhost:{port}/postgres"
        _wait_for_postgres(url)
        yield url
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)


def _wait_for_postgres(url: str, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            psycopg2.connect(url).close()
            return
        except psycopg2.OperationalError:
            time.sleep(0.2)
    raise TimeoutError(f"Postgres never became reachable at {url}")


@pytest.fixture
def db(postgres_url, monkeypatch):
    """Reset the schema and point DATABASE_URL at the test Postgres."""
    monkeypatch.setenv("DATABASE_URL", postgres_url)
    conn = psycopg2.connect(postgres_url)
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(SCHEMA_PATH.read_text())
    finally:
        conn.close()
    return postgres_url
