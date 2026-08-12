"""Tests for `ADR-013`'s mock-scope guard.

The important test in this file is `test_canary_moto_internal_still_flips` -- see its docstring.
Everything else verifies behaviour; that one verifies the *mechanism*, which is the part that
could rot silently on a moto upgrade.
"""

from __future__ import annotations

import pytest
from moto import mock_aws

from fnol_voice_agent.aws.bedrock_router import BotoBedrockConverseClient
from fnol_voice_agent.aws.mock_guard import (
    RealAWSCallInsideMockError,
    assert_real_aws_allowed,
    moto_is_patching,
)
from fnol_voice_agent.knowledge.ingest import BedrockEmbedder, DynamoVectorStore

REGION = "us-west-2"


def test_canary_moto_internal_still_flips() -> None:
    """The guard reads a moto internal (`moto.core.models.botocore_stubber.enabled`), which can
    move between versions. If it moves, `moto_is_patching()` starts returning False forever and
    the guard silently stops guarding -- with no other test going red, because every other test
    in this file would still "pass" (nothing raises when the guard is a no-op that permits).

    This test is the thing that fails instead. It asserts the flag observably flips, so a moto
    upgrade that relocates the internal breaks the build loudly rather than disarming ADR-013.
    """
    assert moto_is_patching() is False
    with mock_aws():
        assert moto_is_patching() is True, (
            "moto is patching but the guard cannot tell. The internal this relies on has "
            "moved -- see ADR-013's 'Mechanism' section and re-point moto_is_patching()."
        )
    assert moto_is_patching() is False


def test_detects_nested_and_decorator_forms() -> None:
    """Nesting and the decorator form are both real usage in this suite, and a guard that only
    understood the plain context-manager form would have a hole exactly where a complicated
    test -- the kind most likely to mix backends by accident -- lives."""

    @mock_aws
    def inside_decorator() -> bool:
        return moto_is_patching()

    assert inside_decorator() is True

    with mock_aws():
        with mock_aws():
            assert moto_is_patching() is True
        # Still patching: the outer scope has not exited yet.
        assert moto_is_patching() is True
    assert moto_is_patching() is False


def test_assert_real_aws_allowed_passes_outside_a_mock_scope() -> None:
    assert_real_aws_allowed("anything") is None  # type: ignore[func-returns-value]


def test_assert_real_aws_allowed_raises_inside_a_mock_scope() -> None:
    with mock_aws():
        with pytest.raises(RealAWSCallInsideMockError) as exc:
            assert_real_aws_allowed("bedrock-runtime / something")
    assert "bedrock-runtime / something" in str(exc.value)
    assert "ADR-013" in str(exc.value)


def test_bedrock_converse_client_refuses_to_construct_inside_a_mock_scope() -> None:
    """The exact Stage 8 bug, as a regression test: this construction previously succeeded and
    the resulting client returned a moto-fabricated 404 that looked like an AWS response."""
    with mock_aws():
        with pytest.raises(RealAWSCallInsideMockError):
            BotoBedrockConverseClient(region=REGION)


def test_bedrock_embedder_refuses_to_construct_inside_a_mock_scope() -> None:
    with mock_aws():
        with pytest.raises(RealAWSCallInsideMockError):
            BedrockEmbedder(region=REGION)


def test_bedrock_clients_construct_normally_outside_a_mock_scope() -> None:
    """Constructing a boto3 client makes no network call and needs no credentials, so this is
    still a $0.00, offline test -- it proves the guard does not block the legitimate path."""
    assert BotoBedrockConverseClient(region=REGION) is not None
    assert BedrockEmbedder(region=REGION) is not None


def test_dynamodb_paths_are_deliberately_not_guarded() -> None:
    """DynamoDB under moto is the intended, correct substitution -- moto implements it
    faithfully, and this project's default `make ingest` run depends on exactly this. Asserting
    it explicitly so a future well-meaning change that "guards everything for consistency" has
    to delete a test that says why not, rather than silently breaking the default path."""
    with mock_aws():
        store = DynamoVectorStore(table_name="fnol-mock-guard-test", region=REGION)
        store.ensure_table()
        assert moto_is_patching() is True
