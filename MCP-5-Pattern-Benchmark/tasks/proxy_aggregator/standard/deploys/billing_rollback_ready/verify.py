#!/usr/bin/env python3
"""Checks a succeeded production deploy exists for the billing-service repo
(repo_id 1), through the shared Postgres-reading helper.
"""

import sys

from tasks.utils.backend_state import find_deploy_by_repo_and_environment

REPO_ID = 1
ENVIRONMENT = "production"

if __name__ == "__main__":
    deploy = find_deploy_by_repo_and_environment(REPO_ID, ENVIRONMENT)
    ok = deploy is not None and deploy["status"] == "succeeded"
    sys.exit(0 if ok else 1)
