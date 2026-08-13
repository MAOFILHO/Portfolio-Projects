"""`scripts/verify_layer_contents.py::verify_archive_structure` -- `D82`'s regression test. Presence in
the built DIRECTORY and correct path inside the ZIP are different claims; this file only tests the
second, against zips constructed directly with `zipfile` (no real layer build, no AWS).
"""

from __future__ import annotations

import zipfile
from pathlib import Path

from scripts.verify_layer_contents import IMPORT_NAMES, verify_archive_structure


def _make_zip(path: Path, entries: dict[str, str]) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return path


def _all_packages_correctly_nested() -> dict[str, str]:
    """One entry per `IMPORT_NAMES` value, correctly nested under `python/`."""
    entries: dict[str, str] = {}
    for import_name in IMPORT_NAMES.values():
        entries[f"python/{import_name}/__init__.py"] = ""
    return entries


def test_d82_shape_no_python_prefix_at_all(tmp_path: Path) -> None:
    """The exact bug: every package present, at the zip's OWN root, with no `python/` prefix anywhere."""
    entries = {f"{import_name}/__init__.py": "" for import_name in IMPORT_NAMES.values()}
    zip_path = _make_zip(tmp_path / "deps.zip", entries)

    problems = verify_archive_structure(zip_path)

    assert len(problems) == 1
    assert "no entry under a top-level 'python/' prefix" in problems[0]
    assert "D82" in problems[0]


def test_correctly_nested_archive_passes(tmp_path: Path) -> None:
    zip_path = _make_zip(tmp_path / "deps.zip", _all_packages_correctly_nested())

    assert verify_archive_structure(zip_path) == []


def test_one_package_missing_the_python_prefix_is_caught_individually(tmp_path: Path) -> None:
    """A PARTIALLY correct archive -- most packages nested, one not -- must not pass just because the
    `python/` prefix exists somewhere in the zip."""
    entries = _all_packages_correctly_nested()
    # Move pydantic out from under python/ -- simulates a partial/manual repackaging gone wrong.
    del entries["python/pydantic/__init__.py"]
    entries["pydantic/__init__.py"] = ""
    zip_path = _make_zip(tmp_path / "deps.zip", entries)

    problems = verify_archive_structure(zip_path)

    assert len(problems) == 1
    assert "pydantic" in problems[0]
    assert "python/pydantic/" in problems[0]


def test_single_file_module_recognised_at_the_exact_path(tmp_path: Path) -> None:
    """`python/<name>.py` (a single-file module, not a package directory) must also count as present --
    not every import in `IMPORT_NAMES` ships as a directory."""
    entries = _all_packages_correctly_nested()
    del entries["python/yaml/__init__.py"]
    entries["python/yaml.py"] = ""
    zip_path = _make_zip(tmp_path / "deps.zip", entries)

    assert verify_archive_structure(zip_path) == []


def test_missing_archive_file_is_its_own_problem(tmp_path: Path) -> None:
    problems = verify_archive_structure(tmp_path / "does-not-exist.zip")
    assert len(problems) == 1
    assert "does not exist" in problems[0]
