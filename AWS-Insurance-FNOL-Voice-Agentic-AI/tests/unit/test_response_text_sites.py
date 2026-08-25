"""Tests for `redteam/response_text_sites.py`'s AST walker -- proves the mechanism has teeth (finds the
site shapes it claims to, classifies them correctly, and doesn't lose the site the manual sweep missed)
before trusting it to drive `readback_probe.py`'s coverage check.
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from types import ModuleType

import pytest

from redteam.response_text_sites import discover_response_text_sites

_FIXTURE_SOURCE = textwrap.dedent(
    '''
    """A synthetic node-shaped module, exercising every site shape the walker needs to distinguish."""

    _STATIC_PROMPT = "What's your policy number?"
    _PROMPTS_BY_SLOT: dict[str, str] = {"a": "prompt a", "b": "prompt b"}


    def plain_node(state):
        if state.get("waiting"):
            return {"response_text": None}

        if state.get("ask"):
            return {"response_text": _STATIC_PROMPT}

        if state.get("lookup"):
            return {"response_text": _PROMPTS_BY_SLOT[state["slot"]]}

        if state.get("literal"):
            return {"response_text": "a bare literal, inline"}

        try:
            value = do_something(state)
        except ValueError as exc:
            return {"response_text": f"went wrong: {exc}"}

        return {"response_text": f"the value is {value}"}


    def make_factory_node():
        def inner(state):
            return {"response_text": some_call()}

        return inner
    '''
)


@pytest.fixture
def fixture_module(tmp_path: Path) -> ModuleType:
    import importlib.util
    import sys

    module_path = tmp_path / "_response_text_sites_fixture_module.py"
    module_path.write_text(_FIXTURE_SOURCE)
    spec = importlib.util.spec_from_file_location(
        "_response_text_sites_fixture_module", module_path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    yield module
    del sys.modules[spec.name]


def _by_ordinal(sites: list, qualname: str) -> dict[int, object]:
    return {s.ordinal: s for s in sites if s.qualname == qualname}


def test_walker_classifies_none_as_always_none(fixture_module: ModuleType) -> None:
    sites = _by_ordinal(discover_response_text_sites(fixture_module), "plain_node")
    assert sites[1].kind == "always_none"


def test_walker_classifies_a_bare_module_constant_as_constant(fixture_module: ModuleType) -> None:
    sites = _by_ordinal(discover_response_text_sites(fixture_module), "plain_node")
    assert sites[2].kind == "constant"


def test_walker_resolves_a_subscript_into_a_module_level_dict_of_literals_as_constant(
    fixture_module: ModuleType,
) -> None:
    sites = _by_ordinal(discover_response_text_sites(fixture_module), "plain_node")
    assert sites[3].kind == "constant"


def test_walker_classifies_an_inline_string_literal_as_constant(fixture_module: ModuleType) -> None:
    sites = _by_ordinal(discover_response_text_sites(fixture_module), "plain_node")
    assert sites[4].kind == "constant"


def test_walker_finds_the_except_branch_site_and_marks_it_dynamic(
    fixture_module: ModuleType,
) -> None:
    # The exact shape the manual sweep (docs/audits/2026-08-16-d121-guardrail-mechanism-sweep.md) missed
    # on its first pass: an f-string inside an `except` handler, not a `return` statement at the top
    # level of the function.
    sites = _by_ordinal(discover_response_text_sites(fixture_module), "plain_node")
    assert sites[5].kind == "dynamic"
    assert sites[5].branch_kind == "except"


def test_walker_classifies_an_fstring_over_a_local_variable_as_dynamic(
    fixture_module: ModuleType,
) -> None:
    sites = _by_ordinal(discover_response_text_sites(fixture_module), "plain_node")
    assert sites[6].kind == "dynamic"
    assert sites[6].branch_kind == "other"


def test_walker_finds_sites_inside_a_nested_closure_with_a_dotted_qualname(
    fixture_module: ModuleType,
) -> None:
    all_sites = discover_response_text_sites(fixture_module)
    nested = [s for s in all_sites if s.qualname == "make_factory_node.inner"]
    assert len(nested) == 1
    assert nested[0].kind == "dynamic"


def test_walker_ordinals_are_1_indexed_and_stable_in_source_order(
    fixture_module: ModuleType,
) -> None:
    sites = _by_ordinal(discover_response_text_sites(fixture_module), "plain_node")
    assert sorted(sites) == [1, 2, 3, 4, 5, 6]


def test_walker_site_id_combines_module_qualname_and_ordinal(fixture_module: ModuleType) -> None:
    sites = _by_ordinal(discover_response_text_sites(fixture_module), "plain_node")
    assert sites[6].site_id == f"{fixture_module.__name__}::plain_node#6"


# --- Against the real node modules -- a floor, not an exact-count pin: this project's own guard against ---
# --- re-introducing a hand-maintained site list is the coverage check in readback_probe.py, not this test.


@pytest.mark.parametrize(
    "module_path",
    [
        "fnol_voice_agent.agents.nodes.file_auto_claim",
        "fnol_voice_agent.agents.nodes.check_claim_status",
        "fnol_voice_agent.agents.nodes.coverage_question",
        "fnol_voice_agent.agents.nodes.rental_towing",
        "fnol_voice_agent.agents.nodes.update_contact_info",
    ],
)
def test_every_real_node_module_has_at_least_one_dynamic_site(module_path: str) -> None:
    import importlib

    module = importlib.import_module(module_path)
    sites = discover_response_text_sites(module)
    assert any(
        s.kind == "dynamic" for s in sites
    ), f"{module_path}: expected at least one dynamic site"


def test_update_contact_info_py_79_the_erratum_site_is_found_and_marked_dynamic() -> None:
    # docs/audits/2026-08-16-d121-guardrail-mechanism-sweep.md's own erratum: the manual sweep's first
    # pass missed this exact site (an except-branch f-string). The walker must not repeat that miss.
    #
    # Line number moved to 104 (D140/OI58, 2026-08-20): the confirm-ceiling-exhausted branch above this
    # one grew an initiate_escalation() call, shifting every line below it. `lineno` is documented on
    # `ResponseTextSite` itself as "for diagnostics/error messages only -- never part of identity" --
    # this test pinning to one anyway is this test's own pre-existing choice, not touched here beyond the
    # mechanical update; the test NAME keeps the original "79" as a historical pointer to the erratum, not
    # a live claim about today's line number.
    import importlib

    module = importlib.import_module("fnol_voice_agent.agents.nodes.update_contact_info")
    sites = discover_response_text_sites(module)
    except_sites = [s for s in sites if s.branch_kind == "except"]
    assert len(except_sites) == 1
    assert except_sites[0].kind == "dynamic"
    assert except_sites[0].lineno == 104
