from surveil_deploy.state import DeploymentState, delete_state, load_state, save_state


def test_new_state_has_no_completed_steps():
    state = DeploymentState()
    assert not state.is_complete("s00_preflight")


def test_mark_complete_records_outputs():
    state = DeploymentState()
    state.mark_complete("s03_deploy_infra", {"STORAGE_ACCOUNT_NAME": "st123"})
    assert state.is_complete("s03_deploy_infra")
    assert state.resource_outputs["STORAGE_ACCOUNT_NAME"] == "st123"


def test_save_and_load_roundtrip(tmp_state_file):
    state = DeploymentState()
    state.mark_complete("s00_preflight", {})
    state.mark_complete("s01_azure_login", {"AZURE_SUBSCRIPTION_ID": "abc-123"})
    save_state(tmp_state_file, state)

    loaded = load_state(tmp_state_file)
    assert loaded.is_complete("s00_preflight")
    assert loaded.is_complete("s01_azure_login")
    assert loaded.resource_outputs["AZURE_SUBSCRIPTION_ID"] == "abc-123"


def test_load_missing_file_returns_empty_state(tmp_state_file):
    state = load_state(tmp_state_file)
    assert state.completed_steps == {}


def test_load_corrupt_file_returns_empty_state(tmp_state_file):
    tmp_state_file.write_text("{not valid json")
    state = load_state(tmp_state_file)
    assert state.completed_steps == {}


def test_delete_state_removes_file(tmp_state_file):
    save_state(tmp_state_file, DeploymentState())
    assert tmp_state_file.exists()
    delete_state(tmp_state_file)
    assert not tmp_state_file.exists()


def test_reset_clears_state():
    state = DeploymentState()
    state.mark_complete("s00_preflight", {"a": "b"})
    state.reset()
    assert state.completed_steps == {}
    assert state.resource_outputs == {}
