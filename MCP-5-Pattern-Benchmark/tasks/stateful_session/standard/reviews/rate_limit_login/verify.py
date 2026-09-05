#!/usr/bin/env python3
"""Checks the rate_limit_login change request was reviewed and reached verdict
"changes_requested", through the shared Postgres-reading helper.
"""

import sys

from tasks.utils.backend_state import find_change_request_by_title, list_review_comments

TITLE = "Add rate limiting to login endpoint"
COMMENTS = [
    "What's the rate limit threshold?",
    "Please log throttled attempts.",
    "LGTM once logged.",
]

if __name__ == "__main__":
    cr = find_change_request_by_title(TITLE)
    ok = (
        cr is not None
        and cr["status"] == "changes_requested"
        and [c["body"] for c in list_review_comments(cr["id"])] == COMMENTS
    )
    sys.exit(0 if ok else 1)
