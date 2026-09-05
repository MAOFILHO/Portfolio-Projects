#!/usr/bin/env python3
"""Checks Initech's ticket was resolved and routed to standard support,
through the shared Postgres-reading helper.
"""

import sys

from tasks.utils.backend_state import find_ticket_by_title, list_comments

TITLE = "Invoice not received for last billing cycle"
ASSIGNEE = "support-standard"

if __name__ == "__main__":
    ticket = find_ticket_by_title(TITLE)
    ok = (
        ticket is not None
        and ticket["status"] == "resolved"
        and ticket["assignee"] == ASSIGNEE
        and len(list_comments(ticket["id"])) >= 1
    )
    sys.exit(0 if ok else 1)
