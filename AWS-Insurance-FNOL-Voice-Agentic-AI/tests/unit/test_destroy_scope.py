"""The protected-DID checks, run as tests so they cannot be skipped by forgetting a make target.

`scripts/verify_destroy_scope.py` is a CI gate. Wiring it into `make test` as well costs nothing and
removes the failure mode where a control exists but nothing invokes it -- which is the shape of most of
Phase 7's instrument defects.

Each check gets a negative control. A guard that has only ever been seen to pass is not known to work;
Phase 8 Stage 0's `verify-backend` matched a comment instead of a backend block and looked green doing
it, so "it passed" is not evidence about anything.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts import verify_destroy_scope as vds


def test_repo_currently_passes_every_check() -> None:
    """The real repository satisfies all three static protections."""
    assert vds.run() == []


def test_prevent_destroy_is_present_on_the_phone_number() -> None:
    assert vds.check_prevent_destroy() == []


def test_telephony_state_key_is_unique() -> None:
    assert vds.check_state_isolation() == []


def test_no_makefile_recipe_touches_the_telephony_stack() -> None:
    assert vds.check_makefile() == []


def test_prevent_destroy_check_fails_when_it_is_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Negative control: strip `prevent_destroy` and the check must notice."""
    real = (vds.TELEPHONY / "main.tf").read_text()
    fake_dir = tmp_path / "telephony"
    fake_dir.mkdir()
    (fake_dir / "main.tf").write_text(real.replace("prevent_destroy = true", "# removed"))

    monkeypatch.setattr(vds, "TELEPHONY", fake_dir)
    failures = vds.check_prevent_destroy()
    assert failures and "prevent_destroy" in failures[0]


def test_makefile_check_fails_on_a_destroy_target_that_names_telephony(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Negative control: the exact mistake this check exists to catch, written out."""
    bad = tmp_path / "Makefile"
    bad.write_text(
        "destroy:\n"
        "\tcd infra/terraform/stacks/main && terraform destroy\n"
        "\tcd infra/terraform/stacks/telephony && terraform destroy\n"
    )
    monkeypatch.setattr(vds, "MAKEFILE", bad)

    failures = vds.check_makefile()
    assert len(failures) == 1
    assert "destroy" in failures[0]
    assert "stacks/telephony" in failures[0]


def test_makefile_check_ignores_comments_naming_telephony(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A comment explaining the rule is not a violation of it.

    This is the `verify-backend` lesson: that check failed because it matched the words rather than the
    structure. Documentation naming the protected stack is expected and desirable -- the Makefile's own
    `verify-destroy-scope` comment does it -- so matching on text alone would make the correct repository
    fail and pressure someone into deleting the explanation.
    """
    ok = tmp_path / "Makefile"
    ok.write_text(
        "# never let destroy reach infra/terraform/stacks/telephony\n"
        "destroy:\n"
        "\t# not stacks/telephony -- see constraint 16\n"
        "\tcd infra/terraform/stacks/main && terraform destroy\n"
    )
    monkeypatch.setattr(vds, "MAKEFILE", ok)

    assert vds.check_makefile() == []


def test_state_isolation_check_fails_on_a_shared_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Negative control: another stack pointed at telephony's state key."""
    root = tmp_path / "infra" / "terraform"
    tele = root / "stacks" / "telephony"
    other = root / "stacks" / "main"
    tele.mkdir(parents=True)
    other.mkdir(parents=True)

    backend = (
        'terraform {\n  backend "s3" {\n'
        '    bucket = "b"\n'
        '    key    = "stacks/telephony/terraform.tfstate"\n'
        "  }\n}\n"
    )
    (tele / "main.tf").write_text(backend)
    (other / "main.tf").write_text(backend)

    monkeypatch.setattr(vds, "REPO", tmp_path)
    monkeypatch.setattr(vds, "TELEPHONY", tele)

    failures = vds.check_state_isolation()
    assert failures and "shares telephony's state key" in failures[0]
