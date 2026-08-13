# Stage 4 — the missing Lambda dependency layer: plan for review, NOT applied

`D80`/`D81`. Marco's instruction on reviewing `D80`: *"Build the layer and write the plan for my
review — do not apply it."* This document is that plan. **Nothing in it has been applied.** No
`terraform apply` has been run. `did.tf`'s `route_did` gate is untouched. The layer artifact described
below was built and measured **locally, from public PyPI wheels, at zero AWS cost** — no AWS resource
was created to produce these numbers.

---

## 1. Why a layer at all, and why this is the first time it mattered

`infra/terraform/stacks/main/lambda.tf`'s own header comment asserted this would happen at Stage 4 and
never did (`D80`). Stage 3's handler was pure stdlib, so the gap was invisible until Stage 4 added the
real graph (`langgraph`), the escalation schema (`pydantic`), and everything both pull in. The fix is a
`aws_lambda_layer_version` carrying the runtime's third-party dependencies, attached to
`aws_lambda_function.codehook` via `layers = [...]`.

## 2. Platform-matched wheels — the exact risk Marco named, hit and fixed while building this

**Target: Python 3.12, `arm64` (`architectures = ["arm64"]` in `lambda.tf`), CPython ABI `cp312`.**

The build is **not** `pip install <package>` on this (Darwin/arm64) dev machine — that would silently
produce macOS binaries and fail at import on Lambda's Linux runtime exactly as invisibly as `D80` did.
It is a **cross-platform, binary-only resolution against Linux wheels**, using:

```
pip install \
  --platform manylinux2014_aarch64 \
  --platform manylinux_2_28_aarch64 \
  --platform manylinux_2_17_aarch64 \
  --implementation cp --python-version 3.12 --abi cp312 \
  --only-binary=:all: \
  --target ./python \
  <pinned requirements>
```

**Three platform tags, not one, and this is not defensive over-specification — it is a real finding from
actually running the build:**

* `numpy==2.5.2` publishes only `manylinux_2_27_aarch64.manylinux_2_28_aarch64` wheels for this Python
  version — a single `--platform manylinux2014_aarch64` (the older, more commonly-cited tag) resolves
  **zero** matching versions and fails outright.
* `PyYAML==6.0.2` publishes only `manylinux_2_17_aarch64.manylinux2014_aarch64` — the newer tag alone
  fails on this one.
* Amazon Linux 2023 (the Python 3.12 managed runtime's base OS, glibc 2.34) is compatible with all three
  tags; they are not competing choices, they are what each package actually ships.

`--only-binary=:all:` additionally forbids pip from silently falling back to a source build (which
would compile against *this machine's* toolchain/headers and produce exactly the wrong-platform binary
`D80`'s failure mode warns about, while looking like a normal, successful `pip install`). Any package
with no matching wheel for the three tags above **fails the build loudly**, which is the correct failure
mode — a silent fallback is the thing being guarded against.

**This is not a hypothetical risk section — the build failed twice on exactly this axis before
succeeding**, once per package above. Both failures were loud (`ERROR: Could not find a version that
satisfies the requirement`), not silent, because `--only-binary=:all:` was set from the first attempt.

## 3. Size — measured, not asserted

Built and zipped locally (see §7 for exact commands), then measured directly:

| Component | Unzipped | Zipped |
|---|---|---|
| Dependency layer (9 pinned top-level packages + their real transitive closure) | **162 MB** | **54.0 MB** |
| Function code (`src/fnol_voice_agent`, unchanged) | 0.84 MB | 0.128 MB |
| **Combined total** | **≈163 MB** | — |
| **Lambda's unzipped budget (function + all layers combined)** | 250 MB | — |
| **Headroom** | **≈87 MB (35%)** | — |

Source, checked against the AWS Lambda troubleshooting guide rather than assumed: *"The maximum size for
a .zip deployment package for Lambda is 250 MB (unzipped)... this limit applies to the combined size of
all the files you upload, including any Lambda layers."* Direct API/console upload of a `.zip` is capped
at **50 MB zipped** (approximate, base64 framing adds ~30% to the actual request); **this layer's 54.0
MB zip exceeds that** and must be uploaded via S3 (`S3Bucket`/`S3Key`), not Terraform's `filename`
argument — a concrete consequence for §6 below, not a formality.

**`mcp==2.0.0` is excluded from the layer. The method used to decide that, and its blind spot, are stated
explicitly rather than left as "verified" — evidence, not confirmation:**

* **Method: a static source grep.** `grep -rn "^import mcp\b\|^from mcp\." src/ tests/`, restricted to
  imports of the third-party SDK (excluding the project's own `fnol_voice_agent.mcp` namespace). Result:
  zero matches under `src/`; the only match anywhere is `tests/unit/test_mcp_wire_protocol.py`, which
  never runs in Lambda. `pyproject.toml`'s own comment corroborates it independently: `mcp` is "not used
  on the runtime hot path (`ADR-012` keeps that in-process)."
* **The blind spot, named rather than assumed away:** a static grep for `import` statements at the top of
  a file **cannot see a lazy or conditional import** — `if some_condition: import mcp` inside a function
  body, reached only under a runtime condition this grep, and possibly every test, never exercises. That
  shape would produce a `D80`-identical failure: clean build, clean deploy, clean D77-style read-back,
  and a crash the first time a caller's turn happens to take the one branch nobody statically checked —
  possibly the safety path itself, which is the worst place for this exact failure mode to reappear.
* **Mitigation chosen, not merely disclosed: the static claim is backed by a dynamic check, not left to
  stand alone.** §4's execution gate exercises an event matrix covering every code path this project
  has (all six intents, `FallbackIntent`, L1, L3, `injuries_present`) on every deploy. If any of those
  paths contains a conditional `import mcp` the grep missed, that specific gate invocation fails loudly,
  at deploy time, before the layer is ever trusted — not quietly, at an unlucky moment in production,
  which is `D80`'s failure shape exactly. **28 MB against a budget already at 65% utilization does not
  justify shipping `mcp` "to be safe" instead of closing the actual gap** — the gap is closed by the gate
  covering every path, not by the size of what's excluded.

Including `mcp` would have cost **28 MB unzipped / 9 MB zipped** (it pulls a whole ASGI stack —
`starlette`, `uvicorn`, `sse-starlette`, a second `httpx`, `jsonschema`, `cryptography`, `pyjwt`,
`websockets` — for a wire-protocol test the Lambda never runs). It stays in `pyproject.toml`'s main
dependency list (tests need it); it is simply not one of the packages this layer installs.

**Layer contents verified directly, not inferred from a successful build exit code — the sibling risk
to the manylinux finding in §2.** `pip install` exiting 0 is evidence the resolver was satisfied with
*something*, not evidence every expected package landed at the pinned version; a resolver silently
substituting a compatible-but-different version, or a partial/corrupted extraction, would look identical
to success at the shell level. `scripts/verify_layer_contents.py` (new, committed, run against the real
built artifact — not a hypothetical) checks two things per retained package, directly against the
`python/` directory on disk: (1) a `dist-info` entry exists at **exactly** the pinned version, not merely
*a* version; (2) the actual importable module (directory or `.py` file) the metadata claims to provide is
really present, catching a partial extraction that metadata alone would miss.

**Revised on review, 2026-08-13 — presence-and-version is the weaker claim, named directly:** the
manylinux failure in §2 already produced correctly-named files on disk that would have failed to import;
presence alone would not have caught that class of defect if it had landed one platform tag off instead of
zero. The script now attempts a real `importlib.import_module()` of each package, **gated on the running
interpreter actually matching Lambda's target** (`Linux`/`aarch64`/CPython 3.12) — several of these 8
packages ship compiled extensions (`numpy`, `pydantic`'s Rust `pydantic-core`), so an import attempted
under a mismatched platform doesn't degrade to weaker evidence, it fails unconditionally on every possible
input and would train its own reader to ignore it. On a mismatch the import check is **skipped and
reported as skipped**, never silently treated as a pass. **Real result, this session, run against the
built layer on this dev machine (`Darwin arm64, CPython 3.12.13`):** `8/8 expected packages present at
pinned versions`, import check **SKIPPED** — this machine is not the target platform, so nothing has
confirmed these packages import under Lambda. That gap is real and still open; it is closed by §4's
execution gate against the real deployed function, or by the container-image check in §7 as a pre-deploy
alternative — not by this script, on this machine, regardless of how it is written. This script's
contribution is real and narrower than that: did the build put the right things in the box, at the right
version, and (only when it can honestly say so) do they import.

**Not attempted: hand-pruning `langgraph`'s own transitive dependencies** (`langsmith`/`langchain-core`
pull in `zstandard` at 21 MB, the single largest non-numpy/botocore component). Unlike `mcp`, these are
declared transitive requirements of a pinned top-level package this project actually imports at runtime
— selectively removing them would be exactly the kind of manual, unverified surgery that could
reintroduce a `D80`-shaped defect (a lazy import path inside `langgraph` reaching for `langsmith` under
some condition this build never exercised). Flagged as a real, measured optimization opportunity (up to
~20 MB) worth investigating in a follow-up — via `langgraph`'s own extras, if any, or an isolated test
proving the omission is safe — not attempted here under approval pressure.

**Cold-start cost, named rather than ignored:** this moves the deployed package from ~0.85 MB to ~163
MB. `ADR-009`'s mitigation order opens with "smaller package first" as step one of addressing cold
start; this change moves directly against that, because the alternative is a package that cannot run at
all. Phase 9's cold-start measurement (already scoped) should treat this package's actual cold-start
number as new information, not assume `ADR-009`'s existing framing still describes it.

## 4. Permanent import gate — not a throwaway probe, and not fooled by `StatusCode: 200`

**A one-off post-deploy probe fixes today and guarantees `D80` recurs on the next dependency change.**
The gate has to be permanent, in the deploy path, and has to invoke the function.

**The gate cannot trust a 200, and this is stated explicitly rather than left to be discovered the way
`D80` was.** `lambda:Invoke`'s synchronous response carries `StatusCode: 200` for **both** a normal
return **and** an unhandled exception in the function — the failure signal is a separate
`FunctionError` header (`"Unhandled"`/`"Handled"`) plus a structured error object in the payload body,
not the HTTP-adjacent status code. A gate written as `if response["StatusCode"] == 200: pass` would
reproduce `D80` exactly: this session's own diagnostic `boto3.recognize_text()` call never raised either,
for the identical reason one layer up (Lex's `RecognizeText` also returns a normal-looking 200 when its
own downstream codehook invocation fails). **Specification, not left implicit:**

* New script, `scripts/verify_lambda_execution.py`, `make verify-lambda-execution`: real `lambda:Invoke`
  (not `RecognizeText` — this checks the function executes, not that Lex routes to it) against a **matrix**
  of synthetic Lex codehook events, not one. Per invocation, the gate asserts, in order: (a) **`Function
  Error` is absent from the `Invoke` response** — checked first and explicitly, not inferred from the
  absence of a Python exception in the calling script; (b) the response **payload parses** and contains
  the expected `sessionState.dialogAction.type` key with a legal value (`Delegate`/`ElicitSlot`/`Close`) —
  a well-formed-looking body with the wrong shape (e.g. Lambda's own `errorMessage`/`errorType` JSON,
  which *is* valid JSON and would pass a bare "did it parse" check) fails here; (c) a literal marker
  specific to the exercised path (e.g. the `escalate` session attribute for an injury-trigger event, the
  named `slotToElicit` for a slot-eliciting event) proving the intended branch of `_dispatch()` ran, not
  merely that *some* branch returned *something*.
* **The event matrix, not a single no-signal turn — this is also §3's `mcp`-exclusion mitigation, not a
  separate mechanism.** One event per: each of the six in-scope intents' first turn, `FallbackIntent`,
  the raw-text L1 trigger, the raw-text L3 (`agent`) trigger, and the `injuries_present`-confirmed-true
  path (`D79`). Every code path this project has that could contain a conditional or lazily-triggered
  import is exercised by construction, not by hoping a single smoke event happens to cover it.
* Wired into `make deploy` as a **required** step after `terraform apply`, not an optional or manual one.
  A non-zero exit here fails the target. This is the mechanism difference from what happened this
  session: the D77-safe read-back existed and passed; it was never going to catch this, because it
  wasn't asking whether the function executes. This gate asks that question directly, every deploy.
* Real cost of running it: roughly a dozen `lambda:Invoke` calls, no Lex, no Bedrock reached by any
  synthetic event (none are injury phrasings, and the intent-opener events are chosen to resolve before
  any generation step) — effectively free, and orders of magnitude cheaper than finding the same class of
  defect via criterion 9's real `RecognizeText`/Bedrock calls, which is what happened this time.

## 5. Ordering — `D81`'s fix lands first, independent of this layer work

Per Marco's instruction: *"Harness invalid-channel (item 2) lands before any re-run. Otherwise the
re-run cannot produce a reportable `C1` number even if the layer is perfect."* Concretely: `D81`'s
three-state (`escalated`/`not-escalated`/`invalid`) classification and abort-on-invalid behavior in
`scripts/measure_composed_pipeline_deployed.py` do not depend on the layer being built, and are not
gated on it — they can and should be implemented and tested (against the current, still-broken deployed
function, which is a perfect adversarial fixture for exercising the `invalid` path) before or in
parallel with the layer work, not after it. **Sequencing for the actual re-run:**

1. `D81` fix implemented and tested — the three-state classification, the negative-control minimum
   (all 17), **and, per `D81`'s expanded item 4, the two Lambda-side code changes that make provenance
   readable at all**: an `escalation_reason` field written into `sessionAttributes` at the `_close()`
   boundary (sourced from a required caller-supplied argument, not inferred from a nearby log line), and
   `_respond_from_graph_result()`'s escalation branch routed through that same tagging point so the
   graph's in-band detection is no longer the one path with zero provenance signal. This is source code
   in `api/lex_codehook.py`, not only harness code in `scripts/measure_composed_pipeline_deployed.py` —
   both are part of step 1, and both are tested (including a test that today's broken function correctly
   aborts the harness with `invalid`, not a scored 0.000 — the regression test for this exact incident;
   and a test that a fail-closed escalation and a genuine detection produce distinct `escalation_reason`
   values under the still-broken deployed function, the closest available adversarial fixture for it).
2. Layer built (`make build-lambda-layer`) and `scripts/verify_layer_contents.py` passes locally —
   zero AWS cost, catches a silent partial-resolution before anything is uploaded.
3. This layer plan approved by Marco, then applied (`terraform apply`, Marco's to run) —
   **carrying both the dependency layer and step 1's Lambda code change in the same apply.** The re-run
   must not depend on an apply that ships the layer alone: a layer-only apply would leave
   `escalation_reason` unemitted, and a subsequent code-only apply to add it would be a second,
   unplanned change to the exact function this plan is trying to verify, re-opening the same
   read-back question `D77`/`D80` already cost a defect each to close. One apply, both changes, so the
   function measured in step 5 is the one both the layer plan and `D81`'s fix describe.
4. §4's permanent execution gate (the full event matrix, not one smoke event) passes post-apply.
5. Criterion 9 re-run.

Step 5 cannot produce a reportable number without step 1, regardless of how clean steps 2–4 are — a
perfect layer measured by the current harness would report 1.000 with no more evidentiary weight than
this run's 0.000 had, per `D81`'s "a passing run would not have been trustworthy either," and the same is
true if step 1's harness fix lands without its Lambda-side half: a harness that can classify
`escalated`/`not-escalated`/`invalid` but reads an `escalation_reason` field the deployed function never
sets would either see the field absent on every call (indistinguishable from "not implemented," a fourth
unhandled shape) or, worse, silently pass validation against a value that was never actually emitted by
the path it claims to describe. Step 1 is therefore internally sequenced — harness classification,
Lambda field, then the test tying them together — before it counts as done for step 3's purposes. Steps 1
and 2 are independent of each other and can proceed in either order or in parallel; step 3 needs both
done; steps 4–5 are gated on 3.

## 6. Terraform shape (sketch — not written into `lambda.tf`, not applied)

```hcl
# Built by `make build-lambda-layer` (new target), NOT by `archive_file` alone -- the pip cross-platform
# install in §2 is not something Terraform's own data sources do. `archive_file` zips the already-built
# ./layer-build/python directory (deterministic given a locked requirement set) so the resulting hash is
# still content-addressed the way `data.archive_file.codehook` already is.
data "archive_file" "codehook_deps" {
  type        = "zip"
  source_dir  = "${local.repo_root}/.terraform-build/layer/python"
  output_path = "${local.repo_root}/infra/terraform/stacks/main/.terraform-build/lex-codehook-deps.zip"
}

# 54.0 MB zipped -- over the 50 MB direct-upload cap (§3), so S3, not `filename`.
resource "aws_s3_object" "codehook_deps_layer" {
  bucket = aws_s3_bucket.artifacts.id
  key    = "lambda-layers/codehook-deps-${data.archive_file.codehook_deps.output_base64sha256}.zip"
  source = data.archive_file.codehook_deps.output_path
  etag   = data.archive_file.codehook_deps.output_md5
}

resource "aws_lambda_layer_version" "codehook_deps" {
  layer_name          = "${local.name_prefix}-codehook-deps"
  s3_bucket           = aws_s3_bucket.artifacts.id
  s3_key              = aws_s3_object.codehook_deps_layer.key
  compatible_runtimes = ["python3.12"]
  compatible_architectures = ["arm64"]
}

resource "aws_lambda_function" "codehook" {
  # ...unchanged...
  layers = [aws_lambda_layer_version.codehook_deps.arn]
}
```

Combined unzipped total (§3) stays well inside 250 MB with this shape; no other `lambda.tf` resource
needs to change beyond adding `layers = [...]`.

**How this avoids the drift Marco named — "Terraform can miss a changed object" — stated as a chain, not
left implicit.** The mechanism is content-hashing the **object key itself**, not `etag`-based
change-detection on a fixed key:

1. `output_base64sha256` is a hash of the actual zip bytes `archive_file` produced. It changes if and
   only if the layer's contents change.
2. That hash is embedded IN the S3 key (`lambda-layers/codehook-deps-<hash>.zip`), so a content change
   produces a **new object at a new key**, never an in-place overwrite of an old one. There is no
   "did the object at this key change" question for Terraform to get wrong, because a changed layer is,
   by construction, never at the same key as the old one.
3. `aws_lambda_layer_version.codehook_deps`'s `s3_key` argument is a direct reference to that key. A new
   key is a changed input attribute on that resource, which Terraform's plan **cannot** miss — it is not
   inferring drift from a remote read, it is comparing a value it computed itself against state.
4. A changed `s3_key` means `PublishLayerVersion` is called again, which returns a **new, distinct layer
   ARN** (Lambda layer versions are immutable and numbered; there is no "update in place").
5. `aws_lambda_function.codehook.layers` references `aws_lambda_layer_version.codehook_deps.arn`
   directly — not a hardcoded ARN, not a data source re-read — so the new ARN flows into the function's
   own plan automatically, and `terraform apply` updates the function to point at the new layer version
   in the same apply that published it.

The `etag` argument on `aws_s3_object` is kept anyway, but it is belt-and-suspenders for the case where
someone/something changes the S3 object out-of-band without changing the local artifact — not the
mechanism this plan is relying on for the ordinary "I rebuilt the layer" case, which is step 1–2 alone.

## 7. Exact build commands used to produce §3's numbers (reproducible, zero AWS cost)

```bash
pip install \
  --platform manylinux2014_aarch64 --platform manylinux_2_28_aarch64 --platform manylinux_2_17_aarch64 \
  --implementation cp --python-version 3.12 --abi cp312 --only-binary=:all: \
  --target ./python \
  "boto3==1.43.69" "pydantic==2.13.4" "python-dateutil==2.9.0.post0" "openfeature-sdk==0.10.0" \
  "numpy==2.5.2" "langgraph==1.2.11" "langgraph-checkpoint-aws==1.2.1" "PyYAML==6.0.2"
find python -type d -name "__pycache__" -exec rm -rf {} +
find python -type d -name "tests" -exec rm -rf {} +
python3 scripts/verify_layer_contents.py ./python   # 8/8 passed, real output, §3
zip -qr9 lambda-deps-layer.zip python
```

`scripts/verify_layer_contents.py` (§3) is committed now, run this session against the real built
artifact — it is not a proposed check, it is one already written and exercised. Not yet promoted into a
`Makefile` target: proposed as `make build-lambda-layer`, wrapping exactly the sequence above (build,
verify contents, zip) and reading its package list from `pyproject.toml` at build time. The verification
script's own `EXPECTED_PACKAGES` dict stays hand-written and reviewable rather than parsed from
`pyproject.toml`, deliberately — see the script's module docstring — with a proposed unit test asserting
the two stay in sync, so drift between them is a fast local test failure, not a silent gap in the check.

**Recommended, not yet run — a stronger validation than what produced §3's numbers:** the AWS-published
`public.ecr.aws/lambda/python:3.12` container image (`arm64` variant) can run the built layer directory
plus the function code under the *actual* Lambda Python 3.12 execution environment locally, catching any
remaining ABI mismatch before a real deploy. Attempted this session; Docker Desktop's daemon was not
running in this sandbox, so it was not completed. Worth doing once, by Marco or CI, before or instead of
relying on §4's gate to catch it for the first time against the real deployed function.

## 8. Cost of the re-run — first measurement, no carry-forward

Per Marco's instruction, criterion 9's re-run is **not** a continuation of the invalidated run — new
`COSTS.md` line (Line E, not a Line D amendment), estimated before it runs, on the same k=3/26-item
protocol already approved, once `D81`'s harness fix is in place to make the number reportable at all.

---

**Status: plan only. Awaiting Marco's review before any of §6/§7 is applied for real.**
