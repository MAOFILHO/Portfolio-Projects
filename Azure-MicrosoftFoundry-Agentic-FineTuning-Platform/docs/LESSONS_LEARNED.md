[← Back to README](../README.md)

# Lessons Learned

1. **Mock-mode fixtures cannot substitute for live-mode testing, ever** —
   every bug in [Troubleshooting](TROUBLESHOOTING.md) was invisible to 78
   passing unit tests and extensive mock-mode use, because fixture data is
   always well-formed, complete, and fast. Only real Azure responses have
   `null` metrics, async processing races, and "not ready yet" states.
2. **A synchronous SDK call inside an `async def` handler blocks the entire
   process, not just that request** — always wrap blocking I/O (`openai`'s
   sync client, `httpx.get`/`.put`, anything without `await`) in
   `asyncio.to_thread(...)` when it lives inside an async server.
3. **A single blocking request/response is the wrong shape for anything that
   can take longer than a user will wait** — background job + poll (with a
   persisted/resumable job id) is the only pattern that survives a page
   refresh or a lost connection, and it should be the default for any run
   measured in minutes, not an afterthought.
4. **Never index into a dict that might be an `{"error": ...}` payload
   without checking first** — a function that can return either a success
   shape or a graceful error shape needs every caller to check
   `.get("error")` before assuming the success keys exist. One missed check
   turns an expected, documented condition into an unhandled crash.
5. **Don't trust a hand-written TypeScript interface to be honest about
   nullability** — it compiles either way; only real (live-mode) data
   exposes the lie. When a field is genuinely optional/nullable on the wire,
   declare it that way, don't assume the happy-path shape from whatever
   fixture you tested against.
6. **A composite/project-references `tsconfig.json` needs `-b` (build mode)
   to actually check anything** — `tsc --noEmit -p .` against the root
   config silently checks nothing and exits 0. Point directly at the leaf
   config (`tsc --noEmit -p tsconfig.app.json`) for a real check, or verify
   the command actually catches a deliberately-introduced error at least
   once.
7. **In-process caches are invisible across restarts — always add a
   query-Azure-directly fallback for anything load-bearing** — a
   module-level Python variable is fine as a fast path, but if losing it
   means a real, working, already-paid-for resource becomes unusable by the
   app, that's a bug, not an acceptable limitation.
8. **An API that returns synchronously can still be asynchronous underneath —
   verify, don't assume** — Azure's file upload returns immediately but
   validates in the background; referencing the result too early races it.
   When a "create X" call is suspiciously fast for what it claims to do,
   check whether there's a status field to poll before trusting the result
   is ready to use.
9. **A stub that fakes success is worse than one that raises** — the original
   `deploy_finetuned_model` returned a fabricated "Triggered" success payload
   without calling Azure at all, which hid the real gap (no deployment ever
   created) until it was root-caused independently, much later than an
   honest `NotImplementedError` would have surfaced it.
10. **Reproduce frontend bugs with a real browser, not just by reading
    code** — a headless-browser reproduction (Playwright) gave an exact
    stack trace and line number for each crash in this section; guessing
    from the component source alone would have been slower and less certain.
11. **Always confirm before cancelling/deleting anything real, and never
    work around a permission-classifier block** — an accidental test job
    created during raw-payload experimentation was disclosed immediately,
    left running until explicit user confirmation, and cancelled via a
    sanctioned tool (`az rest`) once approved — never by finding a way
    around a blocked action.
12. **A managed platform's built-in feature can have a confirmed, unresolved
    bug for your exact architecture — check the issue tracker, not just the
    docs** — Container Apps Easy Auth 401ing CORS preflights is a known
    limitation with an open GitHub issue, not a misconfiguration. No amount
    of `excludedPaths`/ingress-CORS tuning would have fixed it, because the
    problem is upstream of anything this project's own config controls.
13. **Prefer a library's purpose-built component over hand-rolled state
    logic for anything with a real race condition** — a bespoke
    `loginRedirect()`-in-a-`useEffect` looked correct and even worked
    sometimes, which is worse than failing consistently: it hid a real race
    (`inProgress` state lag on first render) until it recurred in a fresh
    tab. `MsalAuthenticationTemplate` exists specifically because this race
    is common enough to need a maintained, tested answer, not a bespoke one.
14. **When two Terraform resources both touch overlapping remote state,
    expect drift, not a one-time fix** — the same `identifierUris` empty
    bug reproduced twice, independently, after unrelated applies, because
    the actual mechanism (Graph's PATCH behavior on the parent resource)
    was still in play each time. The fix that actually stuck was
    structural (one resource, one field, no separate resource to drift
    from), not a second attempt at the same pattern.
15. **When a live value contradicts your assumption, trust the live value —
    decode the real token/response instead of re-reading documentation a
    third time** — both the issuer-format and audience-claim bugs in this
    section were solved in one step each, the moment an actual issued JWT
    was decoded and inspected directly, after multiple guess-and-redeploy
    cycles based on what the docs implied *should* happen.

---

[← Back to README](../README.md)
