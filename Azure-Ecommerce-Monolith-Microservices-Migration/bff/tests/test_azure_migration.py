"""Unit coverage for the cloud on-demand Container App creation path.
Never touches real Azure — the SDK call itself is monkeypatched out, since
these are unit tests of the wiring (env var gating, registry updates),
not integration tests of azure-mgmt-appcontainers."""
import asyncio

from app import azure_traffic, config
from app.migration_engine import MigrationEngine


def test_is_configured_false_without_env(monkeypatch):
    monkeypatch.delenv("AZURE_RESOURCE_GROUP", raising=False)
    assert azure_traffic.is_configured() is False


def test_is_configured_true_with_env(monkeypatch):
    monkeypatch.setenv("AZURE_RESOURCE_GROUP", "rg-test")
    assert azure_traffic.is_configured() is True


def test_azure_step_creates_container_app_and_updates_registry(monkeypatch):
    monkeypatch.setenv("AZURE_RESOURCE_GROUP", "rg-test")

    async def fake_shift(step_id):
        assert step_id == "extract_user"
        return True, "https://user-service.example.azurecontainerapps.io"

    monkeypatch.setattr(azure_traffic, "shift_traffic_for_step", fake_shift)
    config.RUNTIME_BASE_URLS["user"] = None

    engine = MigrationEngine()
    step = next(s for s in engine.steps if s.id == "extract_user")
    ok = asyncio.run(engine._azure_step(step, "user"))

    assert ok is True
    assert config.RUNTIME_BASE_URLS["user"] == "https://user-service.example.azurecontainerapps.io"


def test_azure_step_reports_clear_error_when_not_configured(monkeypatch):
    monkeypatch.delenv("AZURE_RESOURCE_GROUP", raising=False)

    engine = MigrationEngine()
    step = next(s for s in engine.steps if s.id == "extract_product")
    ok = asyncio.run(engine._azure_step(step, "product"))

    assert ok is False
    assert "make provision" in engine.last_error


def test_decommission_step_clears_monolith_registry_entry(monkeypatch):
    monkeypatch.setenv("AZURE_RESOURCE_GROUP", "rg-test")

    async def fake_shift(step_id):
        assert step_id == "decommission"
        return True, None

    monkeypatch.setattr(azure_traffic, "shift_traffic_for_step", fake_shift)
    config.RUNTIME_BASE_URLS["monolith"] = "https://monolith.example.azurecontainerapps.io"

    engine = MigrationEngine()
    step = next(s for s in engine.steps if s.id == "decommission")
    ok = asyncio.run(engine._execute_step(step, "azure"))

    assert ok is True
    assert config.RUNTIME_BASE_URLS["monolith"] is None


def test_services_endpoint_reports_runtime_registry():
    from fastapi.testclient import TestClient

    from app.main import app

    config.RUNTIME_BASE_URLS["monolith"] = "http://127.0.0.1:6000"
    config.RUNTIME_BASE_URLS["user"] = None

    client = TestClient(app)
    r = client.get("/api/services")

    assert r.status_code == 200
    body = r.json()
    assert body["monolith"] == "http://127.0.0.1:6000"
    assert body["user"] is None


def test_migration_status_reports_mode():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    r = client.get("/api/migration/status")

    assert r.status_code == 200
    assert r.json()["mode"] == config.RUN_MODE
