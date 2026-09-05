# 02: Real backend behind the control server

**What to build:** The synthetic backend for this module: one Postgres
database behind a small HTTP API scoped to the `/tickets` namespace (list,
create, get, update, add comment, add attachment — 6 endpoints), run under
Docker Compose, with a seed script that resets and reloads the schema before
each task. `server_wrapper` is repointed at this real API and its hardcoded
stub is deleted. The single task from Ticket 01 gets a real verification
script that reads final state from Postgres and passes.

**Blocked by:** 01

**Status:** done

- [x] Docker Compose brings up Postgres and the HTTP API together
- [x] The API implements all 6 `/tickets` endpoints
- [x] A seed script resets and reloads the schema before each task run
- [x] `server_wrapper`'s 6 tools call the real API instead of returning hardcoded JSON; the stub code is removed
- [x] The task from Ticket 01 has a real `verify.py` reading Postgres state and passes when the agent completes it correctly

Also wired `ToolOrchestratorStateManager.set_up()` to call the seed script
per task (not its own bullet above, but the seed script is dead without it).
