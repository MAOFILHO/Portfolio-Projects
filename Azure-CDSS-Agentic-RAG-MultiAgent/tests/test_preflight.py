"""Tests for preflight prerequisite checking."""

from __future__ import annotations

from unittest.mock import patch

from cdss_deploy.steps.s00_preflight import _parse_version, _version_gte


def test_parse_version_standard() -> None:
    assert _parse_version("Docker version 24.0.6, build ed223bc") == "24.0.6"


def test_parse_version_python() -> None:
    assert _parse_version("Python 3.12.1") == "3.12.1"


def test_parse_version_az() -> None:
    output = "azure-cli                         2.83.0\ncore                              2.83.0"
    assert _parse_version(output) == "2.83.0"


def test_parse_version_no_match() -> None:
    assert _parse_version("no version here") is None


def test_version_gte_equal() -> None:
    assert _version_gte("3.12.0", "3.12") is True


def test_version_gte_greater() -> None:
    assert _version_gte("3.13.0", "3.12") is True


def test_version_gte_less() -> None:
    assert _version_gte("3.11.0", "3.12") is False


def test_version_gte_major() -> None:
    assert _version_gte("4.0.0", "3.12") is True


def test_version_gte_minor_less() -> None:
    assert _version_gte("2.49.0", "2.50") is False
