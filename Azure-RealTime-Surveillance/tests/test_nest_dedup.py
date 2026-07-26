from main import _RecentEventDeduper


def test_second_call_with_same_key_is_a_duplicate():
    deduper = _RecentEventDeduper(ttl_seconds=300.0)
    assert deduper.seen_before(("device-1", "event-1")) is False
    assert deduper.seen_before(("device-1", "event-1")) is True


def test_different_keys_are_not_duplicates():
    deduper = _RecentEventDeduper(ttl_seconds=300.0)
    assert deduper.seen_before(("device-1", "event-1")) is False
    assert deduper.seen_before(("device-1", "event-2")) is False
    assert deduper.seen_before(("device-2", "event-1")) is False


def test_entries_expire_after_ttl(monkeypatch):
    deduper = _RecentEventDeduper(ttl_seconds=10.0)

    fake_time = [1000.0]
    monkeypatch.setattr("main.time.monotonic", lambda: fake_time[0])

    assert deduper.seen_before(("device-1", "event-1")) is False
    fake_time[0] += 11.0
    assert deduper.seen_before(("device-1", "event-1")) is False
