"""Command-line entry points used by the Makefile."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from typing import Any

from app.config import FIXTURES_DIR, OUTPUTS_DIR, REPO_ROOT, get_settings
from app.telemetry import init_telemetry

logging.basicConfig(level=logging.INFO, format="%(message)s")
_LOG = logging.getLogger("foundry.cli")

_RULE = "─" * 74


def _banner(title: str) -> None:
    _LOG.info("\n%s\n%s\n%s", _RULE, title, _RULE)


# ---------------------------------------------------------------------------
# run-all
# ---------------------------------------------------------------------------
async def _run_all() -> int:
    from app.agents.orchestrator import invoke

    settings = get_settings()
    init_telemetry()
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

    _banner(
        f"Azure Foundry agentic platform — running all workflows "
        f"[mode={settings.demo_mode}, region={settings.azure_location}]"
    )
    if not settings.is_mock:
        _LOG.warning("LIVE MODE: this run bills real tokens.\n")

    titles = {
        "discovery": "Workflow 1 — Model Discovery & Evaluation",
        "finetune": "Workflow 2 — Supervised Fine-Tuning",
        "comparison": "Workflow 3 — Agentic Inference & Comparison",
    }

    failures = 0
    summary: dict[str, Any] = {}

    for demo, title in titles.items():
        _banner(title)
        try:
            state = await invoke(demo, demo=demo)  # type: ignore[arg-type]
        except Exception as exc:
            _LOG.error("  ✗ %s failed: %s", demo, exc)
            failures += 1
            continue

        for line in state.get("trace", []):
            _LOG.info("  · %s", line)

        if state.get("error"):
            _LOG.error("  ✗ %s", state["error"])
            failures += 1
        else:
            _LOG.info("  ✓ complete")

        summary[demo] = state.get("result", {})
        out = OUTPUTS_DIR / f"{demo}.json"
        out.write_text(json.dumps(state.get("result", {}), indent=2, default=str))
        _LOG.info("    → %s", out.relative_to(REPO_ROOT))

    _banner("Summary")
    _print_summary(summary)

    if failures:
        _LOG.error("\n%d workflow(s) failed.", failures)
        return 1

    _LOG.info("\nAll workflows completed.")
    if not settings.is_mock:
        _LOG.warning("\n🔴 Resources are live and billing. Run `make teardown` when done.")
    return 0


def _print_summary(summary: dict[str, Any]) -> None:
    discovery = summary.get("discovery", {})
    if evaluation := discovery.get("evaluation"):
        _LOG.info(
            "  Workflow 1  evaluation %s across %d rows, %d evaluators",
            evaluation.get("overall_score"),
            evaluation.get("row_count", 0),
            len(evaluation.get("evaluators", [])),
        )

    finetune = summary.get("finetune", {})
    if status := finetune.get("status"):
        estimate = finetune.get("cost_estimate", {})
        deployment = finetune.get("deployment", {})
        _LOG.info(
            "  Workflow 2  job %s · trained %s tokens · est $%s · %s tier ($%s/hr)",
            status.get("status"),
            status.get("metrics", {}).get("trained_tokens"),
            estimate.get("estimated_usd"),
            deployment.get("deployment_type"),
            deployment.get("hourly_cost_usd"),
        )

    comparison = summary.get("comparison", {})
    if report := comparison.get("report"):
        _LOG.info(
            "  Workflow 3  fine-tuned %d/%d vs baseline %d/%d on behavioural checks",
            report.get("fine_tuned_total", 0),
            report.get("max_total", 0),
            report.get("baseline_total", 0),
            report.get("max_total", 0),
        )


# ---------------------------------------------------------------------------
# mcp-list
# ---------------------------------------------------------------------------
async def _mcp_list() -> int:
    from app.mcp_clients.registry import list_tools

    tools = await list_tools()
    _banner(f"MCP tools ({len(tools)} across 3 servers)")
    current = ""
    for tool in tools:
        if tool.server != current:
            current = tool.server
            _LOG.info("\n  %s", f"[{current}]")
        params = ", ".join(sorted(tool.input_schema.get("properties", {}))) or "—"
        _LOG.info("    %-28s %s", tool.name, params)
    return 0


# ---------------------------------------------------------------------------
# validate-fixtures
# ---------------------------------------------------------------------------
def _validate_fixtures() -> int:
    from app.schemas.catalog import Leaderboard, ModelCard, ModelComparison
    from app.schemas.evaluation import EvaluationRun, SyntheticDataset
    from app.schemas.finetune import FineTuneJob

    checks: list[tuple[str, Any]] = [
        ("leaderboard.json", Leaderboard),
        ("model_comparison.json", ModelComparison),
        ("finetune_job.json", FineTuneJob),
        ("synthetic_dataset.json", SyntheticDataset),
        ("evaluation_run.json", EvaluationRun),
    ]

    failures = 0
    for name, model in checks:
        path = FIXTURES_DIR / name
        try:
            model.model_validate(json.loads(path.read_text()))
            _LOG.info("  ✓ %s", name)
        except Exception as exc:
            _LOG.error("  ✗ %s: %s", name, str(exc).splitlines()[0])
            failures += 1

    try:
        cards = json.loads((FIXTURES_DIR / "model_cards.json").read_text())
        for card in cards:
            ModelCard.model_validate(card)
        _LOG.info("  ✓ model_cards.json (%d cards)", len(cards))
    except Exception as exc:
        _LOG.error("  ✗ model_cards.json: %s", str(exc).splitlines()[0])
        failures += 1

    if failures:
        _LOG.error("\n%d fixture(s) invalid. Run: python data/build_fixtures.py", failures)
        return 1
    _LOG.info("\nall fixtures valid")
    return 0


# ---------------------------------------------------------------------------
# sync-env — write terraform outputs into .env after provisioning
# ---------------------------------------------------------------------------
def _sync_env() -> int:
    import subprocess

    tf_dir = REPO_ROOT / "infra" / "terraform"
    try:
        raw = subprocess.run(
            ["terraform", f"-chdir={tf_dir}", "output", "-json"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        _LOG.error("could not read terraform outputs: %s", exc)
        return 1

    outputs = {k: v.get("value") for k, v in json.loads(raw).items()}
    mapping = {
        "AZURE_FOUNDRY_ENDPOINT": "foundry_endpoint",
        "AZURE_FOUNDRY_PROJECT_NAME": "project_name",
        "AZURE_RESOURCE_GROUP": "resource_group_name",
        "APPLICATIONINSIGHTS_CONNECTION_STRING": "app_insights_connection_string",
    }

    env_path = REPO_ROOT / ".env"
    lines = env_path.read_text().splitlines() if env_path.exists() else []
    index = {
        line.split("=", 1)[0]: i for i, line in enumerate(lines) if "=" in line and line[0] != "#"
    }

    for key, output_key in mapping.items():
        value = outputs.get(output_key)
        if value is None:
            continue
        entry = f"{key}={value}"
        if key in index:
            lines[index[key]] = entry
        else:
            lines.append(entry)
        _LOG.info("  set %s", key)

    env_path.write_text("\n".join(lines) + "\n")
    _LOG.info("wrote %s", env_path)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.cli")
    parser.add_argument(
        "command",
        choices=["run-all", "mcp-list", "validate-fixtures", "sync-env"],
    )
    args = parser.parse_args(argv)

    if args.command == "run-all":
        return asyncio.run(_run_all())
    if args.command == "mcp-list":
        return asyncio.run(_mcp_list())
    if args.command == "validate-fixtures":
        return _validate_fixtures()
    return _sync_env()


if __name__ == "__main__":
    sys.exit(main())
