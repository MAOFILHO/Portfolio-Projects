#!/usr/bin/env python3
"""Checks the token_expiry change request was reviewed and reached verdict
"approved", through the shared Postgres-reading helper.
"""

import sys

from tasks.utils.backend_state import find_change_request_by_title, list_review_comments

TITLE = "Fix auth token expiry check"
COMMENTS = [
    "Good catch.",
    "LGTM.",
]

if __name__ == "__main__":
    cr = find_change_request_by_title(TITLE)
    ok = (
        cr is not None
        and cr["status"] == "approved"
        and [c["body"] for c in list_review_comments(cr["id"])] == COMMENTS
    )
    sys.exit(0 if ok else 1)
