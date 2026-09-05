#!/usr/bin/env python3
"""Checks the printer-offline incident was created, evidenced, assigned and
notified, through the shared Postgres-reading helper.
"""

import sys

from tasks.utils.backend_state import find_ticket_by_title, list_attachments, list_comments

TITLE = "Office printer offline in Building 3"
ASSIGNEE = "asmith"
FILENAME = "printer_photo.jpg"

if __name__ == "__main__":
    ticket = find_ticket_by_title(TITLE)
    ok = (
        ticket is not None
        and ticket["assignee"] == ASSIGNEE
        and any(a["filename"] == FILENAME for a in list_attachments(ticket["id"]))
        and len(list_comments(ticket["id"])) >= 1
    )
    sys.exit(0 if ok else 1)
