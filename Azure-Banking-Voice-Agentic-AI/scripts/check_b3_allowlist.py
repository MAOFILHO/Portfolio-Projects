#!/usr/bin/env python3
"""B3's static check: no code path may name a realtime OR pinned text (ADR-006) model outside their
allowlists.

Extended 2026-09-18 (ADR-006 Decision 3) from realtime-only to both deployment classes. The pattern
below now matches any gpt-* model id, realtime-shaped or not, and checks it against the union of
boot.py's two allowlists -- one regex, one scan, rather than a second near-duplicate pair for the
text model. Confirmed safe to broaden: no non-realtime gpt-* id existed anywhere in scan_targets()
before this change, so nothing that used to pass silently starts failing here.

Narrowed 2026-09-21 (Phase 8 gate review): a union check cannot tell the two classes apart, so the
text pin's name passed in a realtime code path. It is now also checked *by file* -- the text pin
may be named only in `TEXT_PIN_FILES`, and the realtime pin not at all in `TEXT_ONLY_FILES`.
Adding a legitimate new home for a pin is a deliberate edit to those two sets.

Deliberately independent of the runtime boot guard (`azbank_voice_agent/boot.py`). The guard
proves what is *deployed* is approved; this proves what is *written down in the source* is
approved. Either alone leaves a gap:

  - guard only: a hardcoded model name somewhere in the package would be invisible until the code
    path that uses it actually ran.
  - static only: source can be correct while the live deployment has silently moved.

docs/PLAN.md, Verification: "CI static check enforces B3's allowlist across the tree."

Two separate checks, because a name-only allowlist is precisely the gap R-01 found live (one
model name spanning multiple versions with different retirement dates and rate limits --
docs/phase0/findings.md, "Model pin reconsideration"):

  1. **Name.** Every substring shaped like a realtime model id must be one of the allowed names.
     Catches a hardcoded name that was never approved at all.
  2. **Pair.** Every `(name, version)` written as a literal pair -- the shape `boot.py`'s own pins
     use, and the shape a stray hardcoded pin elsewhere in the package would most plausibly take
     -- must be an exact allowed pair. Catches an approved name carrying an unapproved version,
     which check 1 alone cannot: the name in isolation is legitimate.

**What check 2 does not cover, by design:** a name and version living in separate, unrelated
variables -- concretely, `docs/phase0/wizard/01-provision.sh`'s `MODEL_NAME=`/`MODEL_VERSION=`
bash assignments, several lines apart, with `MODEL_VERSION_OLD="2025-12-15"` (an unapproved
version) sitting nearby unflagged -- has no literal pair for this pattern to find. That gap is
real but not this control's to close -- it is exactly what the *runtime* boot guard exists for,
since it reads the live deployment's actual (name, version) at boot regardless of what any
script's variables say. The two controls are complementary on purpose (see the guard-only/
static-only split above); this scanner does not attempt cross-variable correlation, which would
mean parsing each language's assignment semantics for a case the runtime guard already closes
for real. (Found still open by /code-review of Phase 2 follow-up, 2026-09-07 -- named here
explicitly rather than left as a vague caveat, since the earlier wording didn't say which file or
which residual value.)

Both patterns scan each file's *whole text*, not line by line, so a literal pair split across
lines (a multi-line tuple) is still caught -- line-by-line scanning would have missed it (also
found by that same follow-up review).

Scope: the package source, the provisioning wizard scripts under `docs/*/wizard/*.sh` -- the one
place outside the package that can actually name a model for `az ... deployment create` (found
missing in /code-review of Phase 2, 2026-09-07) -- `voice-agent/Dockerfile` /
`voice-agent/pyproject.toml`, the two files that describe the built image, and (added Phase 7,
2026-09-16) every `infra/**/*.bicep` module: a Bicep `Microsoft.CognitiveServices/accounts/
deployments` resource is exactly as capable of naming an unapproved model as the wizard scripts
already covered, and had no scanner over it until `infra/modules/aoai.bicep` made it a real
possibility rather than a hypothetical one. Narrative docs
(`docs/**/*.md`) are deliberately excluded: `docs/phase0/findings.md` and
`docs/phase1/research-*.md` legitimately discuss the whole model catalog as research record, not
executable configuration, and scanning them would just be noise nobody could act on. Tests are
excluded for a different reason -- test_boot.py has to name rejected models
(`gpt-4o-realtime-preview`, and the 2025-12-15 version of the pinned name) in order to prove they
are rejected. `scripts/` (this file's own directory) is excluded for the identical reason: this
docstring, two paragraphs up, names `gpt-4o-realtime-preview` as a worked example. A checker that
failed on either would be forbidding the thing that explains what it does.

Exit code 0 = clean, 1 = a disallowed model name or an unapproved (name, version) pair is present.
"""
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _scan_utils

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
PACKAGE_ROOT = REPO_ROOT / "voice-agent" / "azbank_voice_agent"

# Anything that looks like a gpt-* model id, realtime-shaped or not -- broadened 2026-09-18 from
# realtime-only so a hardcoded text-model name is caught the same way a hardcoded realtime one is.
MODEL_PATTERN = re.compile(r"\bgpt-[a-z0-9.\-]+\b", re.IGNORECASE)

# A model id and a date-shaped version written together as a literal pair, quoted either way --
# the shape ACTIVE_REALTIME_MODEL / SUCCESSOR_REALTIME_MODEL / ACTIVE_TEXT_MODEL are declared in, in
# boot.py. `\s` spans newlines too, so a pair split across lines (e.g. a wrapped tuple literal) still
# matches -- matched against each file's whole text, not scanned line by line (see main()).
PAIR_PATTERN = re.compile(
    r"""["'](gpt-[a-z0-9.\-]+)["']\s*,\s*["'](\d{4}-\d{2}-\d{2})["']""",
    re.IGNORECASE,
)


def scan_targets():
    """Every file this check reads: the package source, the wizard scripts, and the two files
    describing the built image. Sorted so a run is deterministic and a violations list is stable
    across machines."""
    return sorted([
        *PACKAGE_ROOT.rglob("*.py"),
        *REPO_ROOT.glob("docs/*/wizard/*.sh"),
        *REPO_ROOT.glob("infra/**/*.bicep"),
        REPO_ROOT / "voice-agent" / "Dockerfile",
        REPO_ROOT / "voice-agent" / "pyproject.toml",
    ])


# Which files may name which pin. The name is checked against the union of both allowlists, but a
# name that is legitimate in one file is a defect in another: the text pin in a realtime code path
# (or the realtime pin in the summariser) is exactly the cross-wiring B3 exists to stop, and the
# union alone waved it through -- only the runtime guard would have caught it (Phase 8 gate review,
# 2026-09-21). Paths are relative to the repo root, posix-style.
TEXT_PIN_FILES = frozenset({
    "voice-agent/azbank_voice_agent/boot.py",  # declares both pins and their guards
    "voice-agent/azbank_voice_agent/postcall/summarizer.py",  # the one caller of the text deployment
    "infra/modules/voice-agent.bicep",  # hands the deployment name to the container as an env var
})
TEXT_ONLY_FILES = frozenset({"voice-agent/azbank_voice_agent/postcall/summarizer.py"})


def class_violation(rel_posix, name):
    """Why `name` may not appear in `rel_posix`, or None. `name` is already known to be allowlisted."""
    text_names, realtime_names = allowed_names_by_class()
    if name in text_names and rel_posix not in TEXT_PIN_FILES:
        return f"{name!r} is the text pin (ADR-006), named outside the files that may name it"
    if name in realtime_names and rel_posix in TEXT_ONLY_FILES:
        return f"{name!r} is the realtime pin, named in a text-only file"
    return None


def allowed_names_by_class():
    """`(text names, realtime names)`, read from the guard like every other allowlist here."""
    sys.path.insert(0, str(REPO_ROOT / "voice-agent"))
    from azbank_voice_agent import boot

    return (
        {name.lower() for name, _ in boot.ALLOWED_TEXT_MODELS},
        {name.lower() for name, _ in boot.ALLOWED_REALTIME_MODELS},
    )


def allowed_names():
    """The model names B3 permits, read from the guard itself rather than restated here.

    Reading them from the source of truth is the point: a checker carrying its own copy of the
    allowlist would keep passing after the real allowlist changed.
    """
    return {name for name, _version in allowed_pairs()}


def allowed_pairs():
    """The exact (name, version) pairs B3 permits, read from the guard itself -- the union of both
    allowlists (realtime, ADR-006's text pin), since this scanner no longer distinguishes which
    deployment class a given match belongs to before checking it."""
    sys.path.insert(0, str(REPO_ROOT / "voice-agent"))
    from azbank_voice_agent import boot

    all_pairs = boot.ALLOWED_REALTIME_MODELS | boot.ALLOWED_TEXT_MODELS
    return {(name.lower(), version) for name, version in all_pairs}


def main():
    names_ok = allowed_names()
    pairs_ok = allowed_pairs()
    violations = []

    for path in scan_targets():
        rel = path.relative_to(REPO_ROOT)
        text = path.read_text()

        for match in PAIR_PATTERN.finditer(text):
            name, version = match.group(1), match.group(2)
            if (name.lower(), version) not in pairs_ok:
                reason = f"{name!r} paired with unapproved version {version!r}"
                violations.append(
                    (rel, _scan_utils.lineno(text, match.start()), reason, _scan_utils.flatten(match.group(0)))
                )

        for match in MODEL_PATTERN.finditer(text):
            name = match.group(0).lower()
            found = repr(match.group(0)) if name not in names_ok else class_violation(rel.as_posix(), name)
            if found:
                violations.append(
                    (rel, _scan_utils.lineno(text, match.start()), found, _scan_utils.flatten(match.group(0)))
                )

    return _scan_utils.report(
        violations,
        title="B3 STATIC CHECK FAILED -- model named outside the realtime/text allowlists:",
        footer=(
            f"Allowed (name, version) pairs: {sorted(pairs_ok)}\n"
            "Change the allowlist in azbank_voice_agent/boot.py deliberately, or fix the code path."
        ),
        ok_message=f"B3 static check: ok -- every model named in the tree is allowlisted {sorted(names_ok)}",
    )


if __name__ == "__main__":
    sys.exit(main())
