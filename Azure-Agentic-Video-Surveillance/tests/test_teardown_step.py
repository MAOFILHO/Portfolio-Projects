from surveil_deploy.config import DeployConfig
from surveil_deploy.state import DeploymentState
from surveil_deploy.steps import s12_teardown


def _config() -> DeployConfig:
    return DeployConfig(azure_env_name="testenv", azure_resource_group="testenv-rg")


def test_purge_waits_for_group_deletion_before_checking_soft_deleted_accounts(monkeypatch):
    # Regression test: --purge used to check for soft-deleted Cognitive
    # Services accounts immediately after `az group delete --no-wait`
    # returned, before Azure had actually finished deleting the group -- so
    # it always found nothing (confirmed live). This asserts the group-exists
    # poll runs to completion (false) before the purge check fires.
    exists_calls = {"count": 0}

    def fake_run(command, *args, **kwargs):
        if command[:3] == ["az", "group", "exists"]:
            exists_calls["count"] += 1
            # First call: still deleting. Second call: gone.
            stdout = "true" if exists_calls["count"] == 1 else "false"
            return type("R", (), {"stdout": stdout, "returncode": 0})()
        return type("R", (), {"stdout": "", "returncode": 0})()

    purge_calls = []
    monkeypatch.setattr(s12_teardown, "run_command", fake_run)
    monkeypatch.setattr(s12_teardown.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(s12_teardown, "purge_soft_deleted_vision_accounts", lambda config: purge_calls.append(config))

    s12_teardown.run(_config(), DeploymentState(), purge=True)

    assert exists_calls["count"] == 2
    assert len(purge_calls) == 1


def test_purge_gives_up_after_timeout_without_calling_purge_check(monkeypatch):
    monkeypatch.setattr(s12_teardown, "run_command", lambda command, *a, **k: type("R", (), {"stdout": "true", "returncode": 0})())
    monkeypatch.setattr(s12_teardown.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(s12_teardown, "GROUP_DELETE_POLL_TIMEOUT_SECONDS", 30)
    monkeypatch.setattr(s12_teardown, "GROUP_DELETE_POLL_INTERVAL_SECONDS", 15)

    purge_calls = []
    monkeypatch.setattr(s12_teardown, "purge_soft_deleted_vision_accounts", lambda config: purge_calls.append(config))

    s12_teardown.run(_config(), DeploymentState(), purge=True)

    assert purge_calls == []


def test_no_purge_requested_does_not_wait_for_group_deletion(monkeypatch):
    exists_calls = {"count": 0}

    def fake_run(command, *args, **kwargs):
        if command[:3] == ["az", "group", "exists"]:
            exists_calls["count"] += 1
            return type("R", (), {"stdout": "true", "returncode": 0})()
        return type("R", (), {"stdout": "", "returncode": 0})()

    monkeypatch.setattr(s12_teardown, "run_command", fake_run)
    sleep_calls = []
    monkeypatch.setattr(s12_teardown.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    s12_teardown.run(_config(), DeploymentState(), purge=False)

    assert exists_calls["count"] == 1
    assert sleep_calls == []
