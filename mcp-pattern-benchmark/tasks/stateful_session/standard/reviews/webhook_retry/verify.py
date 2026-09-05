#!/usr/bin/env python3
"""Checks the webhook-retry change request was reviewed with changes
requested, through the shared Postgres-reading helper.
"""

import sys

from tasks.utils.backend_state import find_change_request_by_title, list_review_comments

TITLE = "Add retry to payment webhook"
COMMENTS = [
    "What's the max retry count?",
    "Please add exponential backoff.",
    "LGTM once that's addressed.",
]

if __name__ == "__main__":
    cr = find_change_request_by_title(TITLE)
    ok = (
        cr is not None
        and cr["status"] == "changes_requested"
        and [c["body"] for c in list_review_comments(cr["id"])] == COMMENTS
    )
    sys.exit(0 if ok else 1)
