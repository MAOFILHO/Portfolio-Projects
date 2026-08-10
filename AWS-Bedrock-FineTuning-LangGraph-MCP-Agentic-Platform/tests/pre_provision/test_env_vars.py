import os

REQUIRED_ENV_VARS = [
    "AWS_REGION",
    "PROJECT_SUFFIX",
    "BUDGET_LIMIT_USD",
    "BUDGET_ALERT_EMAIL",
]


def test_required_env_vars_present() -> None:
    missing = [name for name in REQUIRED_ENV_VARS if not os.environ.get(name)]
    assert not missing, f"Missing required env vars: {missing}"
