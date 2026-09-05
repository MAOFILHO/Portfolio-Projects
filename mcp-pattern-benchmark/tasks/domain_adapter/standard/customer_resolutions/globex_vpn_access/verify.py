#!/usr/bin/env python3
"""Checks Globex Industries' ticket was resolved, routed to priority support
and noted, through the shared Postgres-reading helper.
"""

import sys

from tasks.utils.backend_state import find_ticket_by_title, list_comments

TITLE = "VPN access failing for remote team"
ASSIGNEE = "priority-support"

if __name__ == "__main__":
    ticket = find_ticket_by_title(TITLE)
    ok = (
        ticket is not None
        and ticket["status"] == "resolved"
        and ticket["assignee"] == ASSIGNEE
        and any(c["body"].startswith("[PRIORITY]") for c in list_comments(ticket["id"]))
    )
    sys.exit(0 if ok else 1)
