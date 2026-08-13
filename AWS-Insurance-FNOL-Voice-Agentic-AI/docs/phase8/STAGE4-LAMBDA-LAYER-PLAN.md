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

**`mcp==2.0.0` is excluded from the layer, and this is checked, not assumed.** `pyproject.toml`'s own
comment says it is "not used on the runtime hot path (`ADR-012` keeps that in-process)." Verified: no
file under `src/fnol_voice_agent/` imports the `mcp` SDK package (`grep` for `import mcp`/`from mcp.`
outside the project's own `fnol_voice_agent.mcp` namespace returns nothing); only
`tests/unit/test_mcp_wire_protocol.py` does, which never runs in Lambda. Including it would have cost
**28 MB unzipped / 9 MB zipped** (it pulls a whole ASGI stack — `starlette`, `uvicorn`, `sse-starlette`,
a second `httpx`, `jsonschema`, `cryptography`, `pyjwt`, `websockets` — for a wire-protocol test the
Lambda never runs). `mcp` stays in `pyproject.toml`'s main dependency list (tests need it); it is simply
not one of the packages this layer installs.

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

## 4. Permanent import gate — not a throwaway probe

**A one-off post-deploy probe fixes today and guarantees `D80` recurs on the next dependency change.**
The gate has to be permanent, in the deploy path, and has to invoke the function:

* New script, `scripts/verify_lambda_execution.py`, `make verify-lambda-execution`: real `lambda:Invoke`
  (not `RecognizeText` — this checks the function executes, not that Lex routes to it) with a minimal
  synthetic Lex codehook event, asserting: (a) no `FunctionError` in the `Invoke` response, (b) the
  response body is a well-formed `sessionState` object (not Lex's own native fallback shape), and (c) a
  literal string marker proving `_dispatch()` ran (e.g. the fixed `NoInput`/`Delegate` wire shape for a
  no-signal turn). This is a stronger assertion than "no exception" — it is the same "read what is
  actually running" discipline as the `D77` read-back, applied to execution rather than deployment
  status, which is exactly the gap `D80`/§11.1 of `RESULTS.md` names.
* Wired into `make deploy` as a **required** step after `terraform apply`, not an optional or manual one.
  A non-zero exit here fails the target. This is the mechanism difference from what happened this
  session: the D77-safe read-back existed and passed; it was never going to catch this, because it
  wasn't asking whether the function executes. This gate asks that question directly, every deploy.
* Real cost of running it: one `lambda:Invoke`, no Lex, no Bedrock reached by the synthetic event (it is
  deliberately not an injury phrasing) — effectively free, and orders of magnitude cheaper than finding
  the same defect via criterion 9's real `RecognizeText`/Bedrock calls, which is what happened this time.

## 5. Ordering — `D81`'s fix lands first, independent of this layer work

Per Marco's instruction: *"Harness invalid-channel (item 2) lands before any re-run. Otherwise the
re-run cannot produce a reportable `C1` number even if the layer is perfect."* Concretely: `D81`'s
three-state (`escalated`/`not-escalated`/`invalid`) classification and abort-on-invalid behavior in
`scripts/measure_composed_pipeline_deployed.py` do not depend on the layer being built, and are not
gated on it — they can and should be implemented and tested (against the current, still-broken deployed
function, which is a perfect adversarial fixture for exercising the `invalid` path) before or in
parallel with the layer work, not after it. **Sequencing for the actual re-run:**

1. `D81` fix implemented and tested (including a test that today's broken function correctly aborts the
   harness with `invalid`, not a scored 0.000 — the regression test for this exact incident).
2. This layer plan approved by Marco, then applied (`terraform apply`, Marco's to run).
3. §4's permanent gate passes post-apply.
4. Criterion 9 re-run.

Step 4 cannot produce a reportable number without step 1, regardless of how clean steps 2–3 are — a
perfect layer measured by the current harness would report 1.000 with no more evidentiary weight than
this run's 0.000 had, per `D81`'s "a passing run would not have been trustworthy either."

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
zip -qr9 lambda-deps-layer.zip python
```

Not yet promoted to a `Makefile`/`scripts/` target — proposed as `make build-lambda-layer`, wrapping
exactly this, reading the package list from `pyproject.toml` rather than duplicating the pin list by
hand (a second, hand-copied requirement list is its own future `D80` — the pins would drift the moment
`pyproject.toml` changes and nobody remembers to update this file).

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
