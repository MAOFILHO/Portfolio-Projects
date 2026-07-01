"""Step 6: Generate local env files and seed sample data."""

from __future__ import annotations

from cdss_deploy.console import print_substep
from cdss_deploy.runner import run_script


def run(ctx: dict) -> dict:
    config = ctx["config"]
    state = ctx["state"]
    source_dir = ctx["source_dir"]
    rg = config.azure_resource_group
    app_name = state.deployed_resources.get("app_name", "")

    # populate-env.sh
    populate_script = source_dir / "infra" / "scripts" / "populate-env.sh"
    if populate_script.exists():
        print_substep("Generating .env files from deployed resources...", "info")
        result = run_script(populate_script, args=[rg], cwd=source_dir)
        if result.success:
            print_substep("Environment files generated", "ok")
        else:
            print_substep(f"populate-env.sh warning: {result.stderr[-200:]}", "warn")
    else:
        print_substep("populate-env.sh not found, skipping", "warn")

    # seed-data-infra-network.sh
    seed_script = source_dir / "infra" / "scripts" / "seed-data-infra-network.sh"
    if seed_script.exists() and app_name:
        print_substep("Seeding sample data (in-network)...", "info")
        result = run_script(seed_script, args=[rg, app_name], cwd=source_dir, timeout=300)
        if result.success:
            print_substep("Sample data seeded", "ok")
        else:
            print_substep(f"Seeding warning: {result.stderr[-200:]}", "warn")
    elif not app_name:
        print_substep("Container App name not resolved, skipping seed", "warn")
    else:
        print_substep("seed-data-infra-network.sh not found, skipping", "warn")

    return {"success": True}
