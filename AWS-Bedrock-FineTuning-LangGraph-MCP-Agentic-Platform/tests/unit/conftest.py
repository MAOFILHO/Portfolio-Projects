import pytest

# Unit tests must be hermetic: runnable on a fresh clone, in CI, with no .env and no AWS
# credentials. `Settings` has no defaults for these three (deliberately — a random or
# defaulted project_suffix would orphan billable resources), so anything that constructs
# Settings raises ValidationError without them.
#
# These values are fakes. No test in tests/unit may reach AWS, so they are never used to
# name or address a real resource — they exist only to let Settings validate.
HERMETIC_ENV = {
    "PROJECT_SUFFIX": "test-suffix",
    "AWS_REGION": "us-west-2",
    "BUDGET_LIMIT_USD": "25",
    "BUDGET_ALERT_EMAIL": "unit-tests@example.invalid",
}


@pytest.fixture(autouse=True)
def hermetic_settings_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Supplies the required Settings fields for every unit test.

    Applied with monkeypatch so the values are removed afterwards and cannot leak into
    a developer's shell or into the suites that talk to real AWS.
    """
    # pydantic-settings gives real environment variables priority over .env, so these
    # win locally too — the suite behaves identically with or without a developer's .env,
    # which is the point. Do NOT chdir here: scenario configs and dataset paths resolve
    # relative to the repository root.
    for key, value in HERMETIC_ENV.items():
        monkeypatch.setenv(key, value)
