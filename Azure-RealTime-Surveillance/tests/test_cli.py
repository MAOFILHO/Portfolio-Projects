from typer.testing import CliRunner

from surveil_deploy.cli import app

runner = CliRunner()


def test_status_with_no_deployment_reports_nothing_in_progress(tmp_path, monkeypatch):
    # config.state_file() resolves against the module-level REPO_ROOT, not
    # cwd, so isolating this test requires patching that directly -- a plain
    # monkeypatch.chdir(tmp_path) silently falls through to this repo's real
    # deployment_state.json (see src/surveil_deploy/config.py).
    monkeypatch.setattr("surveil_deploy.config.REPO_ROOT", tmp_path)
    monkeypatch.setenv("AZURE_ENV_NAME", "testenv")
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "No deployment in progress" in result.stdout


def test_smoke_test_requires_valid_stage():
    result = runner.invoke(app, ["smoke-test", "--stage", "bogus"])
    assert result.exit_code == 2


def test_teardown_cancelled_when_not_confirmed(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["teardown"], input="n\n")
    assert result.exit_code == 0
    assert "cancelled" in result.stdout.lower()
