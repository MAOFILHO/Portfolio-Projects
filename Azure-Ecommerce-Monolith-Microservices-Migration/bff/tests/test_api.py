from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "service": "bff"}


def test_learn_content_matches_schema():
    r = client.get("/api/learn/content")
    assert r.status_code == 200
    body = r.json()
    assert "advantages" in body
    assert "strangler_fig_steps" in body
    assert len(body["strangler_fig_steps"]) == 7


def test_migration_status_initial_state():
    r = client.post("/api/migration/reset")
    assert r.status_code == 200
    body = r.json()
    assert body["active_backend"] == "monolith"
    assert body["running"] is False
    assert all(s["status"] == "pending" for s in body["steps"])


def test_metrics_latest_404_when_no_results(tmp_path, monkeypatch):
    from app import config

    monkeypatch.setattr(config, "RESULTS_DIR", tmp_path / "no-results-here")
    r = client.get("/api/metrics/latest")
    assert r.status_code == 404


def test_metrics_latest_skips_legacy_file_missing_measured_field(tmp_path, monkeypatch):
    """A result saved before the `measured` field existed must not crash this
    endpoint with a validation error — it should be treated as unusable and
    skipped, same as if no results existed at all."""
    import json

    from app import config

    results_dir = tmp_path / "results"
    results_dir.mkdir()
    legacy = {
        "generated_at": "2026-01-01T00:00:00+00:00",
        "monolith": [{"operation": "list_products", "requests": 10, "p50_ms": 1.0, "p95_ms": 2.0, "throughput_rps": 10.0, "errors": 0}],
        "microservices": [],
    }
    (results_dir / "benchmark_20260101T000000Z.json").write_text(json.dumps(legacy))

    monkeypatch.setattr(config, "RESULTS_DIR", results_dir)
    r = client.get("/api/metrics/latest")
    assert r.status_code == 404


def test_metrics_latest_returns_valid_result_with_partial_measured(tmp_path, monkeypatch):
    """A benchmark run while only one backend was up must be servable as-is —
    no failure, no fabricated data for the missing side."""
    import json

    from app import config

    results_dir = tmp_path / "results"
    results_dir.mkdir()
    monolith_only = {
        "generated_at": "2026-01-01T00:00:00+00:00",
        "measured": ["monolith"],
        "monolith": [{"operation": "list_products", "requests": 10, "p50_ms": 1.0, "p95_ms": 2.0, "throughput_rps": 10.0, "errors": 0}],
        "microservices": [],
    }
    (results_dir / "benchmark_20260101T000000Z.json").write_text(json.dumps(monolith_only))

    monkeypatch.setattr(config, "RESULTS_DIR", results_dir)
    r = client.get("/api/metrics/latest")
    assert r.status_code == 200
    body = r.json()
    assert body["measured"] == ["monolith"]
    assert body["microservices"] == []


def test_metrics_latest_merges_monolith_run_with_later_microservices_run(tmp_path, monkeypatch):
    """The real lifecycle: a benchmark runs once before migration (monolith
    only reachable), then again after migration decommissions the monolith
    (microservices only reachable). Naively returning just the newest file
    would make the "before" bar disappear from the Metrics page the moment
    someone migrates — caught for real running this against Azure. The two
    runs must merge into one result with both sides populated."""
    import json

    from app import config

    results_dir = tmp_path / "results"
    results_dir.mkdir()
    monolith_run = {
        "generated_at": "2026-01-01T00:00:00+00:00",
        "measured": ["monolith"],
        "monolith": [{"operation": "list_products", "requests": 10, "p50_ms": 1.0, "p95_ms": 2.0, "throughput_rps": 10.0, "errors": 0}],
        "microservices": [],
    }
    microservices_run = {
        "generated_at": "2026-01-02T00:00:00+00:00",
        "measured": ["microservices"],
        "monolith": [],
        "microservices": [{"operation": "list_products", "requests": 10, "p50_ms": 3.0, "p95_ms": 4.0, "throughput_rps": 20.0, "errors": 0}],
    }
    (results_dir / "benchmark_20260101T000000Z.json").write_text(json.dumps(monolith_run))
    (results_dir / "benchmark_20260102T000000Z.json").write_text(json.dumps(microservices_run))

    monkeypatch.setattr(config, "RESULTS_DIR", results_dir)
    r = client.get("/api/metrics/latest")
    assert r.status_code == 200
    body = r.json()
    assert set(body["measured"]) == {"monolith", "microservices"}
    assert body["monolith"][0]["p95_ms"] == 2.0
    assert body["microservices"][0]["p95_ms"] == 4.0
