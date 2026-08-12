# Lessons learned

Companion to [`RESULTS.md`](RESULTS.md) and [`INCIDENT-LOG.md`](INCIDENT-LOG.md).
`RESULTS.md` records what the models did; this file records what the *build* did.


Roughly two dozen real defects surfaced in this build. Very few were caught by reading code — most
appeared the first time something ran somewhere new: a fresh venv, a CI runner, a monorepo path, an
account that still had resources in it. They cluster into five patterns, which are more useful than
the individual bugs.

### 1. Resolve resources; never reconstruct their names

**Five separate bugs, one cause.** Bedrock reserves job and custom-model names permanently, so after
ten attempts and a base-model change, the "canonical" name is a name nothing lives under. Every time
code rebuilt an identifier from a pattern instead of looking up the real resource, it broke:

| Where | Symptom |
|---|---|
| `--skip-training` | "no existing custom model" while three `Active` models sat in the account |
| Deploy step | Name collision; the UI wizard could never reach the Compare step |
| Post-run test | Asserted against attempt #1 (`Stopped`) instead of the real job |
| UI job status | `Status: Unknown` for a job that had completed hours earlier |
| `teardown.py` | `KeyError` on `modelDeploymentArn` — the API returns `customModelDeploymentArn` |

I fixed the first four as individual instances before recognising the pattern. The fix is
`find_custom_models()` / `find_jobs()` — prefix resolution against what actually exists.

### 2. Tests can pass for the wrong reason

- **Unit tests needed `.env`.** 48/48 green locally, `ModuleNotFoundError`-adjacent failures in CI.
  They had silently depended on my machine. Proof of the fix was *moving `.env` aside and re-running*
  — not re-running.
- **A test fixture asserted the wrong thing.** `test_pharma_valid_json_parses_cleanly` used
  `"Neurological"` as its happy path — a value not in the controlled vocabulary. It passed only
  because the field was an unconstrained `str`.
- **I clicked through one scenario and concluded three worked.** Pharma had a hand-written
  `active_job.json` override; banking and it_helpdesk did not, and both were broken.

### 3. A verification that cannot fail is worse than none

`verify_empty.py` — the P0 release gate — probed a bucket name missing its Region suffix.
`head_bucket` returned 404, which the gate read as "bucket absent". **It would have certified a clean
teardown while the bucket was live.**

`teardown.py` had never run against real resources; with an empty account the loop body never
executes, so the `KeyError` above stayed invisible through every prior "successful" test.

> A green check on a code path that has never executed is not evidence.

### 4. A schema that checks shape is not checking the contract

`PharmaTriageOutput` typed `event_category` as `str`, so the guard reported **valid** for
`"Neurological"` and `"hepatobiliary"` — values the downstream enum rejects. Constraining it to the
8-term vocabulary moved schema validity from *100% for both models* to **14% base / 86% tuned**.

The headline finding survived and sharpened: fine-tuning never fixed JSON *syntax*; it fixed
conformity to the contract, which was invisible while the schema only described the shape.

### 5. Environment assumptions travel badly

- **Workflows in `<project>/.github/workflows/` never run in a monorepo.** GitHub reads only the
  repository root. No error, no warning — they simply never fire. Now kept in
  `.github/workflows-for-monorepo-root/`, deliberately not a real workflows path, so they cannot look
  installed when they are not.
- **`make setup` never installed the project.** A fresh clone passed lint and mypy (both path-based)
  and failed every test on import. Hidden for the whole build by a one-off `pip install -e .`.
- **Moving the folder broke the venv** — console scripts carry absolute shebangs. The claim that the
  project was "self-contained and renameable" was only true after this was found.
- **Terraform reads *tags* during refresh**, and tag-list APIs are separate IAM actions from the
  describe/get ones. One missing verb failed the entire plan.

### 6. The failure that was never explained

Seven consecutive jobs in `us-east-1` failed across two Nova base models — three stalled at
`trainingDetails: NotStarted` (one for 74 hours), four failed validation in under three minutes with
`"Encountered an internal error."` The eighth attempt, **same dataset byte-for-byte**, succeeded on
the first try in `us-west-2` on Llama 3.3 70B.

**The root cause was never identified.** It was routed around, not fixed. Every hypothesis was
eliminated — AWS's own validator certified the data 189/189, CloudTrail showed zero IAM or S3 drift,
quotas were nowhere near limits, and the identical configuration had succeeded on this account in
April. Changing Region, model family, and provider at once means the successful variable cannot be
isolated.

Full forensics, including S3 output-manifest evidence:
[`docs/INCIDENT-LOG.md`](docs/INCIDENT-LOG.md).

---

---

## And one I caused while fixing another

The job-resolution fix paginates Bedrock's job list. I called it inline from an `async` route, which
blocked the event loop so completely that `/health` stopped responding and the dev server had to be
force-killed. Caught only because I tried to verify the fix against a running server instead of
trusting that it worked.

---
