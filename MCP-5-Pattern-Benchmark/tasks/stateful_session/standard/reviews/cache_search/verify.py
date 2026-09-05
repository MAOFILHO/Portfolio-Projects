#!/usr/bin/env python3
"""Checks the cache_search change request was reviewed and reached verdict
"changes_requested", through the shared Postgres-reading helper.
"""

import sys

from tasks.utils.backend_state import find_change_request_by_title, list_review_comments

TITLE = "Cache product search results"
COMMENTS = [
    "What's the cache TTL?",
    "Please invalidate on inventory update.",
    "LGTM after that.",
]

if __name__ == "__main__":
    cr = find_change_request_by_title(TITLE)
    ok = (
        cr is not None
        and cr["status"] == "changes_requested"
        and [c["body"] for c in list_review_comments(cr["id"])] == COMMENTS
    )
    sys.exit(0 if ok else 1)
