# 02: Full eight-task customer-resolution suite

**What to build:** The remaining 7 tasks under
`tasks/domain_adapter/standard/customer_resolutions/` (8 total with Ticket
01's `acme_printer_fixed`), each a different customer/ticket pair — 4
premium-tier (tagged `[PRIORITY]` note, routed `priority-support`) and 4
standard-tier (routed `support-standard`, no tag) — so both servers run the
identical 8, mirroring Phase 1 ticket 04.

**Blocked by:** 01

**Status:** done

- [x] 8 tasks total: `acme_printer_fixed`, `bobs_password_reset`,
      `globex_vpn_access`, `initech_invoice_missing`, `wayne_camera_offline`,
      `stark_loyalty_points`, `umbrella_rate_limit`, `wonka_printer_jam`
- [x] Shared backend seed extended to 8 customers / 8 tickets (one pair per
      task) so every task acts on its own fixed, pre-linked ticket
- [x] No `description.md` names a tool from either server (checked by
      `test_task_neutrality_domain_adapter.py`)
- [x] Every `verify.py` reads state through `tasks/utils/backend_state.py`,
      same shared helper Tool Orchestrator uses
- [x] `tests/test_verify_customer_resolutions.py` (mirrors
      `test_verify_incidents.py`): each verifier tested against a correctly
      resolved ticket, a never-resolved one, one routed to the wrong queue,
      and (for the 4 premium tasks) one missing its tag

**Regression note:** extending the shared seed from 2 tickets to 8 shifted
every newly-created ticket's id from 3 to 9. Updated the two Phase 1 tests
that hardcoded the old id (`test_server_wrapper.py`,
`test_server_orchestrator.py`) and the two that hardcoded the old 2-ticket
list (`test_seed.py`, `test_server_wrapper.py`'s `list_tickets` test). Full
suite re-run green after each change (96 passed).

**Not done yet:** the paid `--k 3` run across all 8 tasks × both servers,
aggregation, and the neutrality gate applied to real results (Phase 1 ticket
05's equivalent).
