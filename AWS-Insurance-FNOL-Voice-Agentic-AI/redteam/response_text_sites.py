"""`ADR-017` condition part 3 -- programmatic derivation of every `response_text`-assignment site inside a
node module, so `readback_probe.py`'s coverage check cannot silently under-count the way a hand-written
enumeration already has twice on this exact question: the manual 27-site sweep
(`docs/audits/2026-08-16-d121-guardrail-mechanism-sweep.md`) read only `return` statements and missed
`update_contact_info.py:79`, an `except`-branch site, found later by `/grill-with-docs` Round 2's own
erratum. "Someone adds a node, nobody updates the list" is the same failure shape one level up; this module
exists so the site inventory is re-derived from source at test time, not maintained by hand anywhere.

**What counts as a site.** Any dict literal, anywhere in the module's source, with a `"response_text"` key
-- found by walking every `ast.Dict` node rather than by matching against `ast.Return`/`ast.ExceptHandler`
statement shapes specifically. This is deliberately more general than "return statements and except
branches": it also covers a plain assignment later returned (the ADR's own "any other assignment path"),
without needing a separate code path per statement kind, because it never looks at the *parent* statement
at all -- only at the dict literal itself, wherever it lives.

**What "dynamic" means, and why it is allowed to over-count.** `Site.kind` classifies each discovered
site's `response_text` *value* expression, purely from its AST shape -- no execution, no import beyond
`inspect.getsource`:

- `"always_none"` -- the value is the literal `None`. This branch is a "nothing to say yet" signal
  (`agents/graph.py`'s `_after_intent_node`/`_after_update_contact_info` both route a falsy response_text
  to the shared repair node, never to `guardrails_output_check`) -- nothing is ever spoken, so nothing is
  ever guardrail-checked, and the coverage check does not require a probe for it.
- `"constant"` -- a bare string literal, or a bare `Name`/`Subscript` that resolves (one hop, within this
  module only -- see `_resolve_static_string`) to one, or to a dict-of-literal-strings indexed by one.
  Always the same fixed text (or one of a small, fully-enumerable, non-caller-influenced set of fixed
  texts) -- nothing for a caller's own data to leak into. No probe required.
- `"dynamic"` -- everything else: an f-string, a function call, an attribute access, a `Name` that does not
  resolve to a module-level literal. This is the category `readback_probe.py`'s coverage check requires a
  concrete probe for. **Deliberately conservative in the over-inclusive direction**: a `Name`/`Subscript`
  this module fails to resolve statically is marked dynamic even if a human could tell it is actually safe
  -- a missed *safe* site costs one redundant probe; a missed *unsafe* site is the defect this whole
  mechanism exists to prevent recurring. See each classifier docstring for the exact, narrow set of shapes
  resolved as `"constant"` -- nothing beyond one level of module-local aliasing is attempted on purpose.

**`D140`/`OI58` addition (Phase 12): `has_escalation_key` and `is_escalation_shaped`.** Same single AST
walk, two more per-site facts, for `redteam/escalation_coverage.py`'s use, not `readback_probe.py`'s:

- `has_escalation_key` -- the SAME dict literal that carries this `"response_text"` key also carries a
  real `"escalation"` key (present, and not the literal `None` -- `AgentState.escalation` is typed
  `EscalationRecord | None`, so a node could write `"escalation": None` and this must not count as one).
  Purely structural, no content judgment.
- `is_escalation_shaped` -- a keyword heuristic, openly labelled as one: does this site's text (resolved
  through the module-constant/dict-of-literals rule `"constant"` classification uses, extended one hop
  further across a `from X import NAME` boundary -- see `_resolve_imported_string`, needed for real: `
  guardrails_nodes.py`'s correct `check_authority` branch uses `authority.py`'s `ELIGIBILITY_DEFLECTION`
  by import, and without that hop the already-correct site was simply invisible to this classifier rather
  than recognised as compliant -- OR, failing both, the raw `ast.unparse` snippet, which still catches an
  f-string's static text portions, e.g. `file_auto_claim.py`'s except-branch site) contain a
  transfer-promising phrase. The keyword list is short and was built by grepping the actual current corpus
  for every such phrase across `agents/` and `api/lex_codehook.py` (`"connect"` covers "connect you
  with"/"connecting you with"; `"get you to someone"` covers the `_ABSTENTION` family) rather than guessed
  -- see `escalation_coverage.py` for the list and its own verification against known true/false examples.
  **Stated blind spot, not smoothed over**: a value built through a function call, an attribute access, or
  a SECOND import hop (this module's constant imports a name from a THIRD module) whose static source text
  contains neither keyword would not be flagged. None of the current corpus is shaped that way -- verified
  by reading every site by hand while building this -- but a future one built that way needs a human
  reviewer to catch it, not this check.
"""

from __future__ import annotations

import ast
import importlib
import inspect
from dataclasses import dataclass
from types import ModuleType
from typing import Literal

SiteKind = Literal["always_none", "constant", "dynamic"]


@dataclass(frozen=True)
class ResponseTextSite:
    """One `"response_text"` dict-literal site found in a module's source.

    `site_id` is stable under line-shifting edits elsewhere in the file (an ordinal within its enclosing
    function, not a line number) -- `readback_probe.py`'s concrete probes reference sites by `site_id`, and
    a probe mapping keyed on line numbers would silently go stale on the very next unrelated edit to the
    same file.
    """

    module: str
    qualname: str  # dotted, rooted at the outermost function -- e.g. "make_coverage_question_node.coverage_question"
    ordinal: int  # 1-based index of this site among ALL response_text sites in (module, qualname), source order
    lineno: int  # for diagnostics/error messages only -- never part of identity
    branch_kind: Literal["except", "other"]
    kind: SiteKind
    snippet: str  # ast.unparse of the value expression -- for a human-readable report/error message
    # D140/OI58 additions -- see module docstring's "D140/OI58 addition" note for what each means and how
    # each is derived. Defaulted so existing direct-construction call sites (e.g.
    # tests/unit/test_readback_probe.py's phantom_site) don't need updating for an unrelated field.
    has_escalation_key: bool = False
    is_escalation_shaped: bool = False

    @property
    def site_id(self) -> str:
        return f"{self.module}::{self.qualname}#{self.ordinal}"


def _collect_module_string_constants(tree: ast.Module) -> dict[str, ast.expr]:
    """Every top-level `NAME = <expr>` OR `NAME: <type> = <expr>` assignment in the module, keyed by
    `NAME`, value unresolved (the raw RHS AST node) -- resolution happens lazily in
    `_resolve_static_string`, which is what lets a dict-of-literals value resolve through a `Subscript`
    without a second collection pass. Both assignment forms are collected because this project's own node
    modules use both for the same purpose (`file_auto_claim.py`'s `_ELICITATION_PROMPTS: dict[str, str] =
    {...}` is annotated; `update_contact_info.py`'s `_SLOT_PROMPTS = {...}` is not) -- resolving only one
    form would silently over-flag the other as dynamic depending on a stylistic choice unrelated to
    whether the value is actually static.
    """
    consts: dict[str, ast.expr] = {}
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
        ):
            consts[node.targets[0].id] = node.value
        elif (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.value is not None
        ):
            consts[node.target.id] = node.value
    return consts


def _resolve_static_string(node: ast.expr, module_consts: dict[str, ast.expr]) -> bool:
    """True if `node` is provably a plain string with no caller/runtime influence -- a bare string
    literal; a `Name` referring to a module-level `NAME = "literal"`; or a `Subscript` into a module-level
    dict literal (directly, or via one `Name` hop) whose every value is itself provably static by this same
    rule. Recursive, but only ever descends into module-local bindings -- an import from another module, a
    function call, an attribute access, or an f-string all fail to resolve and the caller must treat the
    site as dynamic. This is intentionally shallow: see the module docstring's "why over-count" note.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return True
    if isinstance(node, ast.Name):
        target = module_consts.get(node.id)
        return target is not None and _resolve_static_string(target, module_consts)
    if isinstance(node, ast.Subscript):
        container = node.value
        if isinstance(container, ast.Name):
            resolved_container = module_consts.get(container.id)
        else:
            resolved_container = container
        if isinstance(resolved_container, ast.Dict):
            return all(
                value is not None and _resolve_static_string(value, module_consts)
                for value in resolved_container.values
            )
    return False


def _classify(node: ast.expr, module_consts: dict[str, ast.expr]) -> SiteKind:
    if isinstance(node, ast.Constant) and node.value is None:
        return "always_none"
    if _resolve_static_string(node, module_consts):
        return "constant"
    return "dynamic"


def _collect_module_import_bindings(tree: ast.Module) -> dict[str, tuple[str, str]]:
    """Every top-level `from X.Y import NAME [as ALIAS]` binding, keyed by the local name, value
    `(dotted_module_path, original_name)`. Absolute imports only (`node.level == 0`) and no star imports
    -- every import in this project's `agents`/`agents/nodes` modules is an absolute `from ... import
    NAME` (verified by reading every one of them while building this), so neither gap costs anything
    today; a relative or star import would silently not resolve rather than crash.
    """
    bindings: dict[str, tuple[str, str]] = {}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            for alias in node.names:
                if alias.name != "*":
                    bindings[alias.asname or alias.name] = (node.module, alias.name)
    return bindings


def _resolve_imported_string(source_module_path: str, original_name: str) -> list[str] | None:
    """One-hop resolution across a `from X import NAME` boundary: import `source_module_path`, parse ITS
    source, and resolve `NAME` against ITS OWN top-level constants only -- deliberately not chasing that
    module's own imports in turn, matching `_resolve_static_string`'s already-stated one-hop-only
    philosophy for the module-local case, just extended to cross exactly one file boundary too. Found
    real, not hypothetical: `guardrails_nodes.py`'s `check_authority` branch uses `authority.py`'s
    `ELIGIBILITY_DEFLECTION` by import, and without this hop that already-correct site was invisible to
    `is_escalation_shaped` -- passing for the wrong reason (never classified as escalation-shaped at all)
    rather than the right one (classified, and found to already carry a real `escalation` key).

    Never raises: an import error, a source-read failure, or a name not found in the target module all
    resolve to `None` (unresolvable) so one bad cross-module reference degrades to the dynamic/unparse
    fallback rather than crashing the whole discovery pass.
    """
    try:
        target_module = importlib.import_module(source_module_path)
        target_source = inspect.getsource(target_module)
        target_tree = ast.parse(
            target_source, filename=target_module.__file__ or source_module_path
        )
    except (ImportError, OSError, SyntaxError):
        return None
    target_consts = _collect_module_string_constants(target_tree)
    target_node = target_consts.get(original_name)
    return (
        _static_string_values(target_node, target_consts, None) if target_node is not None else None
    )


def _static_string_values(
    node: ast.expr,
    module_consts: dict[str, ast.expr],
    import_bindings: dict[str, tuple[str, str]] | None = None,
) -> list[str] | None:
    """Every concrete string this node's value could resolve to -- `None` if it isn't statically
    resolvable at all. A bare literal resolves to a one-item list; a `Subscript` into a dict-of-literals
    resolves to every value in that dict, because the runtime key isn't known statically and this
    module's whole bias is toward over-flagging, never under-flagging (see module docstring). A `Name`
    tries the same module's own top-level constants first, then -- unlike `_resolve_static_string`, which
    stops here -- one hop across an import boundary via `_resolve_imported_string`.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, ast.Name):
        target = module_consts.get(node.id)
        if target is not None:
            return _static_string_values(target, module_consts, import_bindings)
        if import_bindings is not None and node.id in import_bindings:
            return _resolve_imported_string(*import_bindings[node.id])
        return None
    if isinstance(node, ast.Subscript):
        container = node.value
        resolved_container = (
            module_consts.get(container.id) if isinstance(container, ast.Name) else container
        )
        if isinstance(resolved_container, ast.Dict):
            values: list[str] = []
            for value in resolved_container.values:
                resolved = (
                    _static_string_values(value, module_consts, import_bindings)
                    if value is not None
                    else None
                )
                if resolved is None:
                    return None  # one unresolved branch means the whole set can't be vouched for
                values.extend(resolved)
            return values
    return None


# D140/OI58: built by grepping the actual corpus (every response_text-shaped string in agents/ as of
# 2026-08-20), not guessed. "connect" alone (not "connect you with") deliberately -- it matches both
# "connect you with" and injury_escalation.py's "connecting you with" without needing two entries.
# "get you to someone" covers the separate _ABSTENTION family (coverage_question.py, rental_towing.py)
# and authority.py's ELIGIBILITY_DEFLECTION. See escalation_coverage.py for the verification against the
# full known corpus (both the sites that must match and the ordinary reprompts that must not).
_ESCALATION_KEYWORDS = ("connect", "get you to someone")


def _is_escalation_shaped(
    node: ast.expr,
    module_consts: dict[str, ast.expr],
    import_bindings: dict[str, tuple[str, str]],
) -> bool:
    resolved = _static_string_values(node, module_consts, import_bindings)
    haystacks = resolved if resolved is not None else [ast.unparse(node)]
    return any(keyword in text.lower() for text in haystacks for keyword in _ESCALATION_KEYWORDS)


def _dict_has_real_escalation_key(node: ast.Dict) -> bool:
    """True if this SAME dict literal also carries a real `"escalation"` key -- present, and not the
    literal `None` (`AgentState.escalation` is typed `EscalationRecord | None`, so a node writing
    `"escalation": None` explicitly must not count as having set one)."""
    for key, value in zip(node.keys, node.values, strict=True):
        if isinstance(key, ast.Constant) and key.value == "escalation" and value is not None:
            if isinstance(value, ast.Constant) and value.value is None:
                continue
            return True
    return False


class _ResponseTextVisitor(ast.NodeVisitor):
    def __init__(
        self,
        module_name: str,
        module_consts: dict[str, ast.expr],
        import_bindings: dict[str, tuple[str, str]],
    ) -> None:
        self._module_name = module_name
        self._module_consts = module_consts
        self._import_bindings = import_bindings
        self._func_stack: list[str] = []
        self._except_depth = 0
        self._ordinals: dict[tuple[str, str], int] = {}
        self.sites: list[ResponseTextSite] = []

    def visit_FunctionDef(
        self, node: ast.FunctionDef
    ) -> None:  # noqa: N802 -- ast.NodeVisitor convention
        self._func_stack.append(node.name)
        self.generic_visit(node)
        self._func_stack.pop()

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:  # noqa: N802
        self._except_depth += 1
        self.generic_visit(node)
        self._except_depth -= 1

    def visit_Dict(self, node: ast.Dict) -> None:  # noqa: N802
        for key, value in zip(node.keys, node.values, strict=True):
            if isinstance(key, ast.Constant) and key.value == "response_text" and value is not None:
                qualname = ".".join(self._func_stack) or "<module>"
                ordinal_key = (self._module_name, qualname)
                self._ordinals[ordinal_key] = self._ordinals.get(ordinal_key, 0) + 1
                self.sites.append(
                    ResponseTextSite(
                        module=self._module_name,
                        qualname=qualname,
                        ordinal=self._ordinals[ordinal_key],
                        lineno=value.lineno,
                        branch_kind="except" if self._except_depth else "other",
                        kind=_classify(value, self._module_consts),
                        snippet=ast.unparse(value),
                        has_escalation_key=_dict_has_real_escalation_key(node),
                        is_escalation_shaped=_is_escalation_shaped(
                            value, self._module_consts, self._import_bindings
                        ),
                    )
                )
        self.generic_visit(node)


def discover_response_text_sites(module: ModuleType) -> list[ResponseTextSite]:
    """Every `response_text` site in `module`, in source order. Covers a plain `return {...}`, a `return`
    inside an `except` block, and any other dict literal assigned to a variable later returned, uniformly
    -- it does not distinguish by *statement kind* the way a `grep -n "return.*response_text"` sweep would
    (see module docstring for the site this exact gap missed)."""
    source = inspect.getsource(module)
    tree = ast.parse(source, filename=module.__file__ or module.__name__)
    module_consts = _collect_module_string_constants(tree)
    import_bindings = _collect_module_import_bindings(tree)
    visitor = _ResponseTextVisitor(module.__name__, module_consts, import_bindings)
    visitor.visit(tree)
    return visitor.sites


__all__ = ["ResponseTextSite", "SiteKind", "discover_response_text_sites"]
