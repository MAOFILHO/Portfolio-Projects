#!/usr/bin/env python3
"""Phase 7 D5's static check: no Bicep module or deploy tooling may create, delete, or replace the
project's ACS phone number, under any flag or mode.

`CLAUDE.md` and `PROJECT_STATE.md` both carry this as a standing stop condition (R-09): ACS's
Canadian geographic-number inventory has been observed to lose entire localities within ~20 minutes,
so an equivalent replacement may not be purchasable if this number is ever lost. Qualitatively
different from every other resource in this project -- this isn't about cost, it's about
irreplaceability -- so it gets its own static check the same shape as B3's model allowlist: read the
tree, not memory, and fail closed on anything that looks like the forbidden shape.

Three forbidden shapes, independent of each other:

  1. **A Bicep resource block of type `Microsoft.Communication/communicationServices/phoneNumbers`
     that is not `existing`.** Verified live 2026-09-16 (`az provider show --namespace
     Microsoft.Communication`, `infra/modules/acs.bicep`'s own header): this resource type is not
     actually registered by the provider at all, so this pattern can never match anything real --
     the phone number is managed exclusively through ACS's data-plane REST API, outside ARM/Bicep
     entirely. Kept anyway, the same way B3's static check keeps scanning for model names it has
     never seen: failing closed on a shape that currently cannot occur costs nothing and catches the
     day a future API version changes that.
  2. **`az communication phonenumbers` (or `az resource delete` naming that resource type) with a
     purchase/release/cancel/delete verb**, anywhere in a shell script or deploy CLI source file.
  3. **`--mode Complete`, or `DeploymentMode.COMPLETE`/`"Complete"` passed as a deployment mode**,
     anywhere in the tree. Phase 7's own design (D1) already restricts this project to `Incremental`
     deploys everywhere; `Complete` mode deletes any resource not present in the template, so it is
     banned outright rather than trusted to be used carefully near this one resource.

Scope: every `.bicep` file under `infra/`, every `.sh` script anywhere in the project (deploy/
teardown tooling lives in shell or Python, not yet settled which), and every `.py` file under a
`cli/` or `deploy/` directory if one exists yet. This file's own docstring is excluded from itself by
construction -- it names the forbidden patterns in prose, in a comment, never as executable Bicep,
CLI code, or `az` invocation, so nothing above should ever match here.

Exit code 0 = clean, 1 = a forbidden shape is present.
"""
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _scan_utils

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
THIS_FILE = pathlib.Path(__file__).resolve()

PHONE_NUMBER_RESOURCE_TYPE = "Microsoft.Communication/communicationServices/phoneNumbers"

# A Bicep `resource` declaration of the phone-number type that is NOT immediately followed by the
# `existing` keyword -- `resource <name> 'Microsoft.Communication/.../phoneNumbers@<api>' existing = {`
# is the one permitted shape (a read-only reference to what already exists); anything else declares
# it as a managed resource this template can create, update, or (under Complete mode) delete.
BICEP_MANAGED_PHONE_NUMBER_PATTERN = re.compile(
    r"resource\s+\w+\s+'" + re.escape(PHONE_NUMBER_RESOURCE_TYPE) + r"@[^']*'\s*(?!existing)",
)

# `az communication phonenumbers <verb> ...` where verb purchases, releases, cancels, or deletes a
# number, in a shell script or embedded in a Python string building such a command.
PHONE_NUMBER_CLI_VERB_PATTERN = re.compile(
    r"az\s+communication\s+phonenumbers\s+(purchase|release|cancel|delete)",
    re.IGNORECASE,
)

# `az resource delete` naming the phone-number resource type explicitly.
RESOURCE_DELETE_PATTERN = re.compile(
    r"az\s+resource\s+delete\b[^\n]*" + re.escape(PHONE_NUMBER_RESOURCE_TYPE),
    re.IGNORECASE,
)

# Deployment mode Complete, in any of the three shapes this project's tooling might take it: the
# `az deployment group create --mode Complete` CLI flag, or the Python SDK's
# `DeploymentMode.COMPLETE` / a bare `"Complete"` string passed as a mode value.
COMPLETE_MODE_PATTERN = re.compile(
    r"--mode(?:=|\s+)Complete\b|DeploymentMode\.COMPLETE|deployment_mode\s*=\s*[\"']Complete[\"']",
)


def scan_targets():
    """Every file this check reads, sorted so a run is deterministic. `infra/` Bicep, every shell
    script in the project, and the deploy CLI's own source. Settled 2026-09-18 as `src/azbank_deploy/`
    (docs/PLAN.md "Project layout") -- `cli/` and `deploy/` are kept too, harmlessly, rather than
    removed, in case either is ever used for something else in this monorepo."""
    targets = set()
    targets.update(REPO_ROOT.glob("infra/**/*.bicep"))
    targets.update(p for p in REPO_ROOT.rglob("*.sh") if ".venv" not in p.parts)
    targets.update(p for p in REPO_ROOT.rglob("cli/**/*.py") if ".venv" not in p.parts)
    targets.update(p for p in REPO_ROOT.rglob("deploy/**/*.py") if ".venv" not in p.parts)
    targets.update(p for p in REPO_ROOT.glob("src/azbank_deploy/**/*.py") if ".venv" not in p.parts)
    targets.discard(THIS_FILE)
    return sorted(targets)


def main():
    violations = []

    for path in scan_targets():
        rel = path.relative_to(REPO_ROOT)
        text = path.read_text()

        for pattern, reason in (
            (BICEP_MANAGED_PHONE_NUMBER_PATTERN, "phone-number resource declared as managed (not 'existing')"),
            (PHONE_NUMBER_CLI_VERB_PATTERN, "az communication phonenumbers purchase/release/cancel/delete"),
            (RESOURCE_DELETE_PATTERN, "az resource delete targeting the phone-number resource type"),
            (COMPLETE_MODE_PATTERN, "deployment mode Complete"),
        ):
            for match in pattern.finditer(text):
                violations.append(
                    (rel, _scan_utils.lineno(text, match.start()), reason, _scan_utils.flatten(match.group(0)))
                )

    return _scan_utils.report(
        violations,
        title="D5 PHONE-NUMBER SAFETY CHECK FAILED -- forbidden shape found:",
        footer=(
            "The ACS phone number is never released, created, or placed under Complete-mode "
            "deployment, by any script, at any phase, for any reason (R-09, CLAUDE.md)."
        ),
        ok_message="D5 phone-number safety check: ok -- no forbidden create/delete/Complete-mode shape found",
    )


if __name__ == "__main__":
    sys.exit(main())
