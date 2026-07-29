from __future__ import annotations

import json

from surveil_core.storage import SurveillanceStorage


class _FakePages:
    """Stand-in for the `ItemPaged.by_page()` iterator: one page, no
    continuation token, matching the shape `query_events` consumes.
    """

    def __init__(self, items: list[dict]) -> None:
        self._pages = iter([items])
        self.continuation_token = None

    def __iter__(self):
        return self

    def __next__(self):
        return next(self._pages)

    def by_page(self, continuation_token=None):
        return self


class _FakeTableClient:
    def __init__(self, items: list[dict]) -> None:
        self.items = items
        self.last_filter: str | None = None
        self.last_params: dict | None = None
        self.list_entities_called = False

    def query_entities(self, query_filter, parameters=None, results_per_page=None):
        self.last_filter = query_filter
        self.last_params = parameters
        return _FakePages(self.items)

    def list_entities(self, results_per_page=None):
        self.list_entities_called = True
        return _FakePages(self.items)


def _storage_with_fake_table(items: list[dict]) -> tuple[SurveillanceStorage, _FakeTableClient]:
    storage = SurveillanceStorage.__new__(SurveillanceStorage)
    fake = _FakeTableClient(items)
    storage._events_table = fake
    return storage, fake


def test_query_events_builds_parameterized_filter_not_string_interpolation():
    items = [{"PartitionKey": "cam1", "RowKey": "1", "AnalyzedAt": "2026-01-01T00:00:00", "MatchedTags": "[]", "Severity": "low"}]
    storage, fake = _storage_with_fake_table(items)

    storage.query_events(camera_id="cam1", severity="low")

    assert fake.last_filter == "PartitionKey eq @camera_id and Severity eq @severity"
    assert fake.last_params == {"camera_id": "cam1", "severity": "low"}


def test_query_events_with_no_filters_uses_list_entities():
    items = [{"PartitionKey": "cam1", "RowKey": "1", "AnalyzedAt": "2026-01-01T00:00:00", "MatchedTags": "[]"}]
    storage, fake = _storage_with_fake_table(items)

    results, token = storage.query_events()

    assert fake.list_entities_called is True
    assert len(results) == 1
    assert token is None


def test_query_events_tag_filter_is_applied_client_side():
    items = [
        {"PartitionKey": "cam1", "RowKey": "1", "AnalyzedAt": "2026-01-01T00:00:00", "MatchedTags": json.dumps(["person"])},
        {"PartitionKey": "cam1", "RowKey": "2", "AnalyzedAt": "2026-01-02T00:00:00", "MatchedTags": json.dumps(["crowd"])},
    ]
    storage, _ = _storage_with_fake_table(items)

    results, _ = storage.query_events(tags=["crowd"])

    assert len(results) == 1
    assert results[0]["RowKey"] == "2"


def test_query_events_sorts_newest_first():
    items = [
        {"PartitionKey": "cam1", "RowKey": "1", "AnalyzedAt": "2026-01-01T00:00:00", "MatchedTags": "[]"},
        {"PartitionKey": "cam1", "RowKey": "2", "AnalyzedAt": "2026-01-02T00:00:00", "MatchedTags": "[]"},
    ]
    storage, _ = _storage_with_fake_table(items)

    results, _ = storage.query_events()

    assert [r["RowKey"] for r in results] == ["2", "1"]
